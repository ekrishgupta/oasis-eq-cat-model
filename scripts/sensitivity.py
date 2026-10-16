"""Sensitivity of the headline results to each modelling assumption (one at a time).

This does not change the model: the baseline is our result, and each case changes one
assumption to show how far the numbers move. For speed it recomputes mean event losses
directly (TIV x Hazus mean damage ratio per cell, class and design level) instead of
re-running Oasis; the printed check shows the baseline reproduces the Oasis event means.
Metrics use mean event losses and the UCERF3 band rates:
  AAL      sum_e rate_e * L_e
  VaR200   loss of the event at which the cumulative annual rate of larger-or-equal events
           first reaches -ln(1 - 1/200)  (OEP, no secondary uncertainty)
  P50      1 - exp(-sum of rates of events with L_e > $50B)

Inputs:  data/hazus/csm/*.csv, data/hazus/component_repair_cost_ratio.csv,
         outputs/hazard/cell_median_sa.csv, outputs/rates/event_rates.csv,
         data/interim/la_buildings.parquet (or the v1.0 release asset)
Outputs: outputs/sensitivity/sensitivity.csv, outputs/sensitivity/event_losses.csv
"""
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_vulnerability_csm import CLASSES, DURATIONS, STATES  # noqa: E402
from hazus_csm import ELASTIC_DAMPING, CapacityCurve, duration_class, performance_point, state_probabilities  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CSM = ROOT / "data/hazus/csm"
OUT = ROOT / "outputs/sensitivity"
BASE_MIX = {"PC": 0.15, "MC": 0.50, "HC": 0.35}
THRESHOLD = 50e9


@dataclass
class Case:
    name: str
    group: str
    cost_factor: float = 1.0                      # replacement cost per sqft multiplier
    mix: dict = field(default_factory=lambda: dict(BASE_MIX))
    rate_factor: float = 1.0                      # share of band events that hit the scenario location
    elastic_damping: dict = field(default_factory=dict)  # overrides of B_E by Hazus type
    duration: str | None = None                   # force one duration class for every event
    bilinear: bool = False                        # straight-line yield-to-ultimate capacity curve
    beta_factor: float = 1.0                      # scale all fragility dispersions


class BilinearCurve(CapacityCurve):
    def __init__(self, dy, ay, du, au):
        self.dy, self.ay, self.du, self.au, self.k = dy, ay, du, au, ay / dy

    def accel(self, d):
        d = np.asarray(d, float)
        line = self.ay + (self.au - self.ay) * (d - self.dy) / (self.du - self.dy)
        return np.where(d <= self.dy, self.k * d, np.where(d >= self.du, self.au, line))


def load():
    idx = ["building_type", "design_level"]
    tabs = {n: pd.read_csv(CSM / f"{n}.csv").set_index(idx)
            for n in ["capacity", "kappa", "fragility_str", "fragility_nsd", "fragility_nsa"]}
    tabs["cost"] = pd.read_csv(ROOT / "data/hazus/component_repair_cost_ratio.csv").set_index(["component", "occupancy"])
    b = pd.read_parquet(ROOT / "data/interim/la_buildings.parquet", columns=["areaperil_id", "hazus_class", "building_tiv"])
    tiv = b.groupby(["areaperil_id", "hazus_class"])["building_tiv"].sum().unstack(fill_value=0)
    sa = pd.read_csv(ROOT / "outputs/hazard/cell_median_sa.csv").set_index("areaperil_id").loc[tiv.index]
    events = pd.read_csv(ROOT / "outputs/rates/event_rates.csv").set_index("event_id")
    return tabs, tiv, sa, events


def mean_damage(tabs, case: Case, cls, level, duration, sas, sa1):
    btype, occ = CLASSES[cls]
    c = tabs["capacity"].loc[(btype, level)]
    curve = (BilinearCurve if case.bilinear else CapacityCurve)(c.Dy_in, c.Ay_g, c.Du_in, c.Au_g)
    b_e = case.elastic_damping.get(btype, ELASTIC_DAMPING[btype])
    d, a = performance_point(curve, b_e, tabs["kappa"].loc[(btype, level), duration], sas, sa1, DURATIONS[duration])
    mdr = np.zeros(len(sas))
    for comp, table, x, unit in (("STR", "fragility_str", d, "sd_in"), ("NSD", "fragility_nsd", d, "sd_in"),
                                 ("NSA", "fragility_nsa", a, "a_g")):
        r = tabs[table].loc[(btype, level)]
        med = [r[f"{s}_median_{unit}"] for s in STATES]
        beta = [r[f"{s}_beta"] * case.beta_factor for s in STATES]
        lr = np.concatenate([[0], tabs["cost"].loc[(comp, occ), ["DS1-Theta_0", "DS2-Theta_0",
                                                                 "DS3-Theta_0", "DS4-Theta_0"]].to_numpy(float)])
        mdr += state_probabilities(x, med, beta) @ lr
    return np.minimum(mdr, 1.0)


def event_losses(tabs, tiv, sa, events, case: Case) -> pd.Series:
    losses = {}
    for eid, ev in events.iterrows():
        duration = case.duration or duration_class(ev.magnitude)
        sas, sa1 = sa[f"sa03_event_{eid}"].to_numpy(), sa[f"sa10_event_{eid}"].to_numpy()
        total = 0.0
        for cls in tiv.columns:
            mdr = sum(w * mean_damage(tabs, case, cls, lv, duration, sas, sa1) for lv, w in case.mix.items())
            total += (tiv[cls].to_numpy() * mdr).sum()
        losses[eid] = total * case.cost_factor
    return pd.Series(losses)


def metrics(losses: pd.Series, rates: pd.Series) -> dict:
    order = losses.sort_values(ascending=False).index
    cum = rates[order].cumsum()
    target = -np.log(1 - 1 / 200)
    var200 = losses[order][cum >= target].iloc[0] if (cum >= target).any() else 0.0
    return {"aal_bn": (rates * losses).sum() / 1e9, "var200_bn": var200 / 1e9,
            "p_gt_50bn": 1 - np.exp(-rates[losses > THRESHOLD].sum())}


CASES = [
    Case("Baseline (our results)", "baseline"),
    Case("Replacement cost -25%", "Exposure value", cost_factor=0.75),
    Case("Replacement cost +25%", "Exposure value", cost_factor=1.25),
    Case("Newer stock (5/35/60% PC/MC/HC)", "Design-level mix", mix={"PC": 0.05, "MC": 0.35, "HC": 0.60}),
    Case("Older stock (30/50/20% PC/MC/HC)", "Design-level mix", mix={"PC": 0.30, "MC": 0.50, "HC": 0.20}),
    Case("Half of band events hit the city", "Rate attribution", rate_factor=0.5),
    Case("Quarter of band events hit the city", "Rate attribution", rate_factor=0.25),
    Case("All events moderate duration", "Shaking duration", duration="moderate"),
    Case("All events long duration", "Shaking duration", duration="long"),
    Case("Wood damping 10% (AEBM low end)", "Elastic damping", elastic_damping={"W1": 10.0, "W2": 10.0}),
    Case("Steel 7%, concrete 10% (high end)", "Elastic damping",
         elastic_damping={"S1H": 7.0, "PC1": 10.0, "C2L": 10.0, "C2M": 10.0}),
    Case("Bilinear capacity curve", "Capacity curve shape", bilinear=True),
    Case("Fragility beta x0.8", "Fragility dispersion", beta_factor=0.8),
    Case("Fragility beta x1.2", "Fragility dispersion", beta_factor=1.2),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tabs, tiv, sa, events = load()
    rows, all_losses = [], {}
    for case in CASES:
        losses = event_losses(tabs, tiv, sa, events, case)
        all_losses[case.name] = losses / 1e9
        rows.append({"case": case.name, "group": case.group,
                     **metrics(losses, events["annual_rate"] * case.rate_factor)})
        print(f"{case.name:40s} " + "  ".join(f"{k}={v:,.3f}" for k, v in rows[-1].items()
                                               if k not in ("case", "group")))
    pd.DataFrame(rows).to_csv(OUT / "sensitivity.csv", index=False, float_format="%.4f")
    el = pd.DataFrame(all_losses)
    el.insert(0, "event", events["name"])
    el.to_csv(OUT / "event_losses.csv", float_format="%.2f")

    oasis = pd.read_csv(ROOT / "outputs/oasis_run/gul_S1_melt.csv").query("SampleType == 1").set_index("EventId")["MeanLoss"] / 1e9
    print("\nBaseline vs Oasis event means ($bn):")
    print(pd.DataFrame({"sensitivity": all_losses["Baseline (our results)"].round(1), "oasis": oasis.round(1)}).to_string())


if __name__ == "__main__":
    main()
