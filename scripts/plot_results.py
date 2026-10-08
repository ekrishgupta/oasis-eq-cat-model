"""Results chart: loss by scenario (with external benchmarks) and the OEP curve with VaR.

The EP curve is drawn from Oasis's per-event samples with the Poisson formula
P(annual max loss > x) = 1 - exp(-sum_e rate_e * P(L_e > x)), which reproduces the Oasis
full-uncertainty OEP at the tabulated return periods and fills in between them.
Writes outputs/results/results.png.
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams["text.parse_math"] = False  # dollar signs are currency, not math

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/results"
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
BLUE, ORANGE = "#2a78d6", "#eb6834"
# Approximate 2026-dollar building-loss benchmarks (see docs/step5_results.md for sources).
BENCHMARKS_BN = {1: 1.0, 4: 90.0, 8: 70.0}


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)


def main() -> None:
    scen = pd.read_csv(OUT / "scenario_losses.csv", index_col=0)
    summary = json.loads((OUT / "summary.json").read_text())
    selt = pd.read_csv(ROOT / "outputs/oasis_run/gul_S1_selt.csv").query("SampleId > 0")
    rates = scen["annual_rate"]

    fig, (a, b) = plt.subplots(1, 2, figsize=(14, 5.6), facecolor=SURFACE, gridspec_kw={"width_ratios": [1.1, 1]})

    # Panel 1: scenario losses.
    labels = [f"M{r.magnitude} {r.name.replace(' (scenario)', '*')}" for r in scen.itertuples()]
    y = np.arange(len(scen))[::-1]
    a.barh(y, scen["mean_loss_usd_bn"], color=BLUE, height=0.6)
    for yi, (eid, r) in zip(y, scen.iterrows()):
        a.text(r.mean_loss_usd_bn + 2, yi, f"${r.mean_loss_usd_bn:,.0f}B", va="center", fontsize=8.5, color=INK)
        if eid in BENCHMARKS_BN:
            a.plot(BENCHMARKS_BN[eid], yi, "D", ms=7, color=ORANGE, markeredgecolor=SURFACE, markeredgewidth=1.5,
                   label="Benchmark (approx., 2026 $)" if eid == 1 else None)
    a.set_yticks(y, labels, fontsize=9, color=INK)
    a.set_xlabel("Ground-up building loss ($bn)", color=MUTED)
    a.set_title("Loss by earthquake (Hazus capacity spectrum)", loc="left", fontsize=11, color=INK)
    a.legend(frameon=False, fontsize=8.5, loc="lower right")
    style(a)

    # Panel 2: OEP curve.
    x = np.linspace(0, 230e9, 600)
    p_ex = selt.groupby("EventId")["Loss"].apply(lambda s: np.array([(s > xi).mean() for xi in x]))
    lam = sum(rates[e] * p for e, p in p_ex.items())
    with np.errstate(divide="ignore"):
        rp = 1 / (1 - np.exp(-lam))
    ok = np.isfinite(rp)
    b.plot(rp[ok], x[ok] / 1e9, color=BLUE, linewidth=2)
    b.set_xscale("log")
    b.set_xlim(5, 2000)
    ticks = [10, 25, 50, 100, 250, 500, 1000]
    b.set_xticks(ticks, [str(t) for t in ticks])
    b.minorticks_off()
    for k, v in summary["var_oep_usd_bn"].items():
        b.plot(int(k), v, "o", ms=6, color=BLUE, markeredgecolor=SURFACE, markeredgewidth=1.5)
        b.annotate(f"1-in-{k}: ${v:,.0f}B", (int(k), v), xytext=(-8, 8 if k != "200" else -16),
                   textcoords="offset points", ha="right", fontsize=8.5, color=INK)
    b.axhline(50, color=ORANGE, linewidth=1.2, linestyle="--")
    p50 = summary["p_annual_event_loss_gt_50bn"]["analytic"]
    b.text(6, 53, f"$50B: P = {p50:.1%} per year (1-in-{1 / p50:.0f})", fontsize=8.5, color=INK)
    b.set_xlabel("Return period (years, log scale)", color=MUTED)
    b.set_ylabel("Largest event loss in a year ($bn)", color=MUTED)
    b.set_title("Occurrence exceedance probability (OEP) curve", loc="left", fontsize=11, color=INK)
    style(b)

    fig.suptitle(f"LA County earthquake model: 2.42M buildings, $3.35T value; AAL ${summary['aal_usd_bn']:.1f}B",
                 x=0.01, ha="left", fontsize=13, fontweight="bold", color=INK)
    fig.text(0.01, 0.005, "*USGS scenario. Oasis LMF 2.5; USGS ShakeMaps; FEMA Hazus 6.1; UCERF3 LA-region rates; "
             "Microsoft building footprints. The curve flattens above ~$186B because the catalogue has 8 events.",
             fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.savefig(OUT / "results.png", dpi=160, facecolor=SURFACE)
    print(f"wrote {OUT / 'results.png'}")


if __name__ == "__main__":
    main()
