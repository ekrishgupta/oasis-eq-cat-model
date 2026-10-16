"""Tornado chart: how far each assumption moves AAL, the 1-in-200 VaR and P(loss > $50B).

Reads outputs/sensitivity/sensitivity.csv, writes outputs/sensitivity/tornado.png.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams["text.parse_math"] = False

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/sensitivity"
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
LOWER, HIGHER = "#2a78d6", "#eb6834"
METRICS = [("aal_bn", "Average annual loss ($bn)", "${:,.1f}B"),
           ("var200_bn", "1-in-200 VaR ($bn)", "${:,.0f}B"),
           ("p_gt_50bn", "P(event loss > $50B) per year", "{:.1%}")]


def main() -> None:
    s = pd.read_csv(OUT / "sensitivity.csv")
    base = s[s["group"] == "baseline"].iloc[0]
    cases = s[s["group"] != "baseline"]
    # Order groups by their swing in the 1-in-200 VaR.
    swing = cases.groupby("group")["var200_bn"].agg(lambda v: (v - base["var200_bn"]).abs().max())
    groups = swing.sort_values().index.tolist()

    fig, axes = plt.subplots(1, 3, figsize=(16, 6.2), facecolor=SURFACE, sharey=True)
    for ax, (col, title, fmt) in zip(axes, METRICS):
        ax.set_facecolor(SURFACE)
        for y, g in enumerate(groups):
            labelled = []
            for _, r in cases[cases["group"] == g].iterrows():
                v, b = r[col], base[col]
                ax.barh(y, v - b, left=b, height=0.55, color=LOWER if v < b else HIGHER, alpha=0.9)
                close = any(abs(v - u) < 0.03 * abs(b) for u in labelled)
                if abs(v - b) > 1e-9 and not close:
                    labelled.append(v)
                    ax.text(v, y, " " + fmt.format(v) + " ", va="center", fontsize=7.5, color=INK,
                            ha="left" if v > b else "right")
        ax.axvline(base[col], color=INK, linewidth=1)
        ax.set_title(f"{title}\nbaseline {fmt.format(base[col])}", loc="left", fontsize=10, color=INK)
        ax.grid(True, axis="x", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for sp in ("top", "right", "left"):
            ax.spines[sp].set_visible(False)
        ax.spines["bottom"].set_color(GRID)
        ax.tick_params(colors=MUTED, labelsize=8.5)
        lo, hi = cases[col].min(), cases[col].max()
        pad = (hi - lo) * 0.28
        ax.set_xlim(lo - pad, hi + pad)
        if col == "p_gt_50bn":
            ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))

    labels = []
    for g in groups:
        names = cases[cases["group"] == g]["case"].tolist()
        labels.append(f"{g}\n" + " / ".join(names))
    axes[0].set_yticks(np.arange(len(groups)), labels, fontsize=8, color=INK)
    fig.suptitle("Sensitivity of the results to each assumption (one at a time)", x=0.01, ha="left",
                 fontsize=13, fontweight="bold", color=INK)
    fig.text(0.01, 0.01, "Blue = assumption lowers the metric, orange = raises it. P(> $50B) jumps in steps "
             "because Whittier Narrows ($46B) and Long Beach ($58B) sit either side of $50B.",
             fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 0.94))
    fig.savefig(OUT / "tornado.png", dpi=150, facecolor=SURFACE)
    print(f"wrote {OUT / 'tornado.png'}")


if __name__ == "__main__":
    main()
