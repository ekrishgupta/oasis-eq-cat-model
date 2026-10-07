"""Map the median PGA of each scenario over the LA model grid (small multiples).

Reads outputs/hazard/cell_median_pga.csv and data/events.csv,
writes outputs/hazard/footprint_maps.png.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/hazard"
INK, MUTED, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"

# Sequential: one hue, light -> dark, shared scale across all panels.
CMAP = LinearSegmentedColormap.from_list("pga", ["#fdf3ec", "#f6b48f", "#eb6834", "#a8360f", "#4a1404"])
VMAX = 0.7
PLACES = {"Downtown": (-118.25, 34.05), "Santa Monica": (-118.49, 34.02),
          "Long Beach": (-118.19, 33.77), "Pasadena": (-118.14, 34.15),
          "Northridge": (-118.54, 34.23), "Lancaster": (-118.14, 34.69)}


def main() -> None:
    cells = pd.read_csv(OUT / "cell_median_pga.csv")
    events = pd.read_csv(ROOT / "data/events.csv")
    lons, lats = np.sort(cells["lon"].unique()), np.sort(cells["lat"].unique())

    fig, axes = plt.subplots(2, 4, figsize=(16, 8.6), facecolor=SURFACE)
    for ax, ev in zip(axes.ravel(), events.itertuples()):
        grid = cells.pivot(index="lat", columns="lon", values=f"pga_event_{ev.event_id}")
        im = ax.pcolormesh(lons, lats, grid.to_numpy(), cmap=CMAP, vmin=0, vmax=VMAX, shading="nearest")
        for name, (x, y) in PLACES.items():
            ax.plot(x, y, "o", ms=2.5, color=INK)
            ax.annotate(name, (x, y), xytext=(3, 2), textcoords="offset points", fontsize=6.5, color=INK)
        kind = " (scenario)" if "scenario" in ev.name else f", {int(ev.year)}"
        name = ev.name.replace(" (scenario)", "")
        ax.set_title(f"M{ev.magnitude}  {name}{kind}", loc="left", fontsize=9.5, color=INK)
        ax.text(0.02, 0.03, f"max {grid.to_numpy().max():.2f} g", transform=ax.transAxes,
                fontsize=8, color=MUTED)
        ax.set_aspect(1 / np.cos(np.radians(34.2)))
        ax.set_xticks([]), ax.set_yticks([])
        for s in ax.spines.values():
            s.set_color("#e4e3df")

    cbar = fig.colorbar(im, ax=axes, orientation="horizontal", fraction=0.035, pad=0.04, extend="max")
    cbar.set_label("Median peak ground acceleration (g), USGS ShakeMap", color=MUTED)
    cbar.ax.tick_params(colors=MUTED, labelsize=8)
    cbar.outline.set_visible(False)
    fig.suptitle("Hazard footprints: how hard each earthquake shakes Los Angeles County",
                 x=0.01, ha="left", fontsize=13, fontweight="bold", color=INK)
    fig.text(0.01, 0.01, "0.01-degree (~1 km) model grid. Historical events: USGS ShakeMap Atlas; "
             "scenarios: USGS ShakeOut. Ridgecrest and Kern County epicentres are 150-200 km north.",
             fontsize=7.5, color=MUTED)
    fig.savefig(OUT / "footprint_maps.png", dpi=150, bbox_inches="tight", facecolor=SURFACE)
    print(f"wrote {OUT / 'footprint_maps.png'}")


if __name__ == "__main__":
    main()
