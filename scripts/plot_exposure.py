"""Map building replacement value per 1 km hazard cell, and write the per-cell totals.

Reads data/interim/la_buildings.parquet and model_data/areaperil_grid.json,
writes outputs/exposure/tiv_by_cell.csv and outputs/exposure/exposure_map.png.
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, LogNorm

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/exposure"
INK, MUTED, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"
CMAP = LinearSegmentedColormap.from_list("tiv", ["#e8f0fb", "#9cc0ee", "#2a78d6", "#174a8c", "#0a2447"])
PLACES = {"Downtown": (-118.25, 34.05), "Santa Monica": (-118.49, 34.02),
          "Long Beach": (-118.19, 33.77), "Pasadena": (-118.14, 34.15),
          "Northridge": (-118.54, 34.23), "Lancaster": (-118.14, 34.69)}


def main() -> None:
    grid = json.loads((ROOT / "model_data/areaperil_grid.json").read_text())
    b = pd.read_parquet(ROOT / "data/interim/la_buildings.parquet",
                        columns=["areaperil_id", "building_tiv"])
    cells = b.groupby("areaperil_id").agg(buildings=("building_tiv", "size"),
                                          tiv_usd=("building_tiv", "sum")).reset_index()
    cells.to_csv(OUT / "tiv_by_cell.csv", index=False)

    n_rows, n_cols, step = grid["n_rows"], grid["n_cols"], grid["step"]
    img = np.full(n_rows * n_cols, np.nan)
    img[cells["areaperil_id"] - 1] = cells["tiv_usd"] / 1e9
    img = img.reshape(n_rows, n_cols)
    lons = grid["lon_min"] + (np.arange(n_cols) + 0.5) * step
    lats = grid["lat_min"] + (np.arange(n_rows) + 0.5) * step

    fig, ax = plt.subplots(figsize=(9, 8.2), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    im = ax.pcolormesh(lons, lats, img, cmap=CMAP, norm=LogNorm(vmin=0.01, vmax=img[~np.isnan(img)].max()),
                       shading="nearest")
    for name, (x, y) in PLACES.items():
        ax.plot(x, y, "o", ms=3, color="#eb6834")
        ax.annotate(name, (x, y), xytext=(4, 3), textcoords="offset points", fontsize=8, color=INK)
    ax.set_aspect(1 / np.cos(np.radians(34.2)))
    ax.set_xticks([]), ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    cbar = fig.colorbar(im, ax=ax, orientation="horizontal", fraction=0.04, pad=0.03)
    cbar.set_label("Building replacement value per ~1 km cell ($bn, log scale)", color=MUTED)
    cbar.ax.tick_params(colors=MUTED, labelsize=8)
    cbar.outline.set_visible(False)
    total = cells["tiv_usd"].sum() / 1e12
    ax.set_title(f"LA County exposure: {cells['buildings'].sum() / 1e6:.2f}M buildings, "
                 f"${total:.2f} trillion replacement value", loc="left", fontsize=12,
                 fontweight="bold", color=INK)
    fig.text(0.02, 0.01, "Microsoft Global ML Building Footprints, clipped to mainland LA County; "
             "value = floor area x replacement cost per sqft.", fontsize=7.5, color=MUTED)
    fig.savefig(OUT / "exposure_map.png", dpi=150, bbox_inches="tight", facecolor=SURFACE)
    print(f"{len(cells):,} occupied cells; top cell ${cells['tiv_usd'].max() / 1e9:.1f}bn")


if __name__ == "__main__":
    main()
