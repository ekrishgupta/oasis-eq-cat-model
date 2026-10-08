"""Turn the Oasis ORD outputs into the project deliverables.

  scenario losses   mean and spread of ground-up building loss per event (moment ELT)
  EP curves         Oasis full-uncertainty OEP and AEP (from the 100,000-year catalogue)
  VaR               loss at the 1-in-100, 1-in-200 and 1-in-250 year return periods
  P(loss > $50B)    probability of at least one $50B+ event in a year (OEP) and of $50B+
                    total in a year (AEP), checked two ways:
                      analytic   1 - exp(-sum_e rate_e * P(L_e > x)), P from Oasis samples
                      simulated  share of the 100,000 simulated years above x

Inputs:  outputs/oasis_run/gul_S1_{melt,selt,ept,palt}.csv, data/events.csv,
         outputs/rates/event_rates.csv, model_data/occurrence_lt.csv
Outputs: outputs/results/{scenario_losses,ep_curve,var}.csv, outputs/results/summary.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "outputs/oasis_run"
OUT = ROOT / "outputs/results"
THRESHOLD = 50e9
VAR_RPS = [100, 200, 250]
EP_CALC = {1: "mean_damage", 2: "full_uncertainty", 3: "per_sample_mean", 4: "sample_mean"}
EP_TYPE = {1: "OEP", 2: "OEP_TVaR", 3: "AEP", 4: "AEP_TVaR"}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    events = pd.read_csv(ROOT / "outputs/rates/event_rates.csv").set_index("event_id")
    melt = pd.read_csv(RUN / "gul_S1_melt.csv").query("SampleType == 2").set_index("EventId")
    selt = pd.read_csv(RUN / "gul_S1_selt.csv").query("SampleId > 0")
    ept = pd.read_csv(RUN / "gul_S1_ept.csv")
    palt = pd.read_csv(RUN / "gul_S1_palt.csv").query("SampleType == 2").iloc[0]
    occ = pd.read_csv(ROOT / "model_data/occurrence_lt.csv")
    n_years = 100_000

    scen = events[["name", "magnitude", "annual_rate", "return_period_years"]].copy()
    scen["mean_loss_usd_bn"] = melt["MeanLoss"] / 1e9
    scen["sd_loss_usd_bn"] = melt["SDLoss"] / 1e9
    scen["loss_pct_of_tiv"] = 100 * melt["MeanLoss"] / melt["FootprintExposure"]
    scen.round(4).to_csv(OUT / "scenario_losses.csv")

    ept["calc"], ept["type"] = ept["EPCalc"].map(EP_CALC), ept["EPType"].map(EP_TYPE)
    curve = ept.query("calc == 'full_uncertainty' and type in ['OEP', 'AEP']").pivot(
        index="ReturnPeriod", columns="type", values="Loss").sort_index() / 1e9
    curve.to_csv(OUT / "ep_curve.csv", float_format="%.3f")
    var = curve.loc[VAR_RPS].rename_axis("return_period_years")
    var.to_csv(OUT / "var.csv", float_format="%.3f")

    # P(loss > $50B): analytic Poisson over events, using Oasis's per-event samples.
    p_exceed = selt.groupby("EventId")["Loss"].apply(lambda s: (s > THRESHOLD).mean())
    lam = (events["annual_rate"] * p_exceed.reindex(events.index).fillna(0)).sum()
    p_oep_analytic = 1 - np.exp(-lam)
    # Simulated: event mean loss per occurrence, per year max (OEP) and sum (AEP).
    occ["loss"] = occ["event_id"].map(melt["MeanLoss"])
    by_year = occ.groupby("period_no")["loss"]
    p_oep_sim = (by_year.max() > THRESHOLD).sum() / n_years
    p_aep_sim = (by_year.sum() > THRESHOLD).sum() / n_years

    summary = {
        "aal_usd_bn": round(palt["MeanLoss"] / 1e9, 3),
        "var_oep_usd_bn": {int(k): round(v, 1) for k, v in var["OEP"].items()},
        "var_aep_usd_bn": {int(k): round(v, 1) for k, v in var["AEP"].items()},
        "p_annual_event_loss_gt_50bn": {"analytic": round(p_oep_analytic, 4), "simulated": round(p_oep_sim, 4)},
        "p_annual_total_loss_gt_50bn_simulated": round(p_aep_sim, 4),
        "return_period_of_50bn_event_years": round(1 / p_oep_analytic, 1),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print(scen[["name", "magnitude", "mean_loss_usd_bn", "loss_pct_of_tiv", "return_period_years"]]
          .round(2).to_string())
    print(curve.round(1).to_string())
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
