"""Convert USGS ShakeMaps into an Oasis hazard footprint for Los Angeles County.

Model grid: a regular 0.01-degree (~1 km) lon/lat grid over LA County. Each cell is one Oasis
areaperil_id = row * n_cols + col + 1, counted from the south-west corner.

Intensity follows the Hazus capacity spectrum method: for each event and cell we take the
ShakeMap median 5%-damped spectral accelerations at 0.3 s and 1.0 s (grid.xml PSA03, PSA10,
%g -> g), interpolated to the cell centre, plus the event's Hazus duration class (from its
magnitude). That triple maps to one intensity bin of the vulnerability (probability 1).
Ground-motion variability is not added here: the Hazus fragility dispersions already
include demand-spectrum variability, and Hazus itself runs ShakeMaps at their median.

Inputs:  data/events.csv, data/raw/shakemaps/<usgs_id>/grid.xml
Outputs: model_data/footprint.csv, model_data/areaperil_grid.json,
         outputs/hazard/cell_median_pga.csv, outputs/hazard/cell_median_sa.csv,
         outputs/hazard/event_summary.csv
"""
import io
import json
import re
from pathlib import Path

import sys

import numpy as np
import pandas as pd
from scipy.interpolate import RegularGridInterpolator

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_vulnerability_csm import DURATIONS, SA03_EDGES, SA10_EDGES  # noqa: E402
from hazus_csm import duration_class  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/shakemaps"
MODEL = ROOT / "model_data"
OUT = ROOT / "outputs/hazard"

# LA County mainland bounding box (excludes Catalina and San Clemente islands).
GRID = {"lon_min": -118.95, "lat_min": 33.70, "lon_max": -117.65, "lat_max": 34.83, "step": 0.01}


def read_shakemap_xml(path: Path) -> tuple[pd.DataFrame, dict]:
    """Parse a ShakeMap grid/uncertainty XML into a DataFrame plus the grid spec."""
    text = path.read_text()
    names = re.findall(r'<grid_field index="\d+" name="([^"]+)"', text)
    spec = dict(re.findall(r'(\w+)="([^"]+)"', re.search(r"<grid_specification[^>]*>", text).group(0)))
    body = text[text.index("<grid_data>") + len("<grid_data>"):text.index("</grid_data>")]
    df = pd.read_csv(io.StringIO(body), sep=r"\s+", header=None, names=names)
    return df, {k: float(v) for k, v in spec.items()}


def to_interpolator(df: pd.DataFrame, spec: dict, field: str) -> RegularGridInterpolator:
    nlon, nlat = int(spec["nlon"]), int(spec["nlat"])
    # Rows run north to south with longitude fastest; flip to ascending latitude.
    values = df[field].to_numpy().reshape(nlat, nlon)[::-1]
    lats = df["LAT"].to_numpy().reshape(nlat, nlon)[::-1, 0]
    lons = df["LON"].to_numpy().reshape(nlat, nlon)[0, :]
    return RegularGridInterpolator((lats, lons), values, bounds_error=False, fill_value=np.nan)


def model_grid() -> tuple[pd.DataFrame, dict]:
    step = GRID["step"]
    n_cols = int(round((GRID["lon_max"] - GRID["lon_min"]) / step))
    n_rows = int(round((GRID["lat_max"] - GRID["lat_min"]) / step))
    rows, cols = np.meshgrid(np.arange(n_rows), np.arange(n_cols), indexing="ij")
    cells = pd.DataFrame({
        "areaperil_id": (rows * n_cols + cols + 1).ravel(),
        "lon": (GRID["lon_min"] + (cols.ravel() + 0.5) * step).round(4),
        "lat": (GRID["lat_min"] + (rows.ravel() + 0.5) * step).round(4),
    })
    return cells, GRID | {"n_cols": n_cols, "n_rows": n_rows,
                          "areaperil_id": "row * n_cols + col + 1, row/col from south-west"}


def spectral_bin(sa03: np.ndarray, sa10: np.ndarray, duration: str) -> np.ndarray:
    """Intensity bin id for (SA(0.3 s), SA(1.0 s), duration); values outside the grid clamp."""
    n03, n10 = len(SA03_EDGES) - 1, len(SA10_EDGES) - 1
    i = np.clip(np.searchsorted(SA03_EDGES, sa03, side="right") - 1, 0, n03 - 1)
    j = np.clip(np.searchsorted(SA10_EDGES, sa10, side="right") - 1, 0, n10 - 1)
    return list(DURATIONS).index(duration) * n03 * n10 + i * n10 + j + 1


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    events = pd.read_csv(ROOT / "data/events.csv")
    cells, grid_meta = model_grid()
    pts = cells[["lat", "lon"]].to_numpy()

    footprint, pga, sa, summary = [], {}, {}, []
    for ev in events.itertuples():
        grid_df, spec = read_shakemap_xml(RAW / ev.usgs_id / "grid.xml")
        med = {f: to_interpolator(grid_df, spec, f)(pts) / 100.0 for f in ("PGA", "PSA03", "PSA10")}
        if any(np.isnan(v).any() for v in med.values()):
            raise ValueError(f"{ev.usgs_id}: ShakeMap does not cover the whole LA grid")
        duration = duration_class(ev.magnitude)
        pga[ev.event_id] = med["PGA"]
        sa[f"sa03_event_{ev.event_id}"], sa[f"sa10_event_{ev.event_id}"] = med["PSA03"], med["PSA10"]
        footprint.append(pd.DataFrame({
            "event_id": ev.event_id,
            "areaperil_id": cells["areaperil_id"].to_numpy(),
            "intensity_bin_id": spectral_bin(med["PSA03"], med["PSA10"], duration),
            "probability": 1.0,
        }))
        summary.append({
            "event_id": ev.event_id, "name": ev.name, "magnitude": ev.magnitude, "duration": duration,
            "max_pga_g": med["PGA"].max().round(3), "mean_pga_g": med["PGA"].mean().round(3),
            "max_sa03_g": med["PSA03"].max().round(3), "max_sa10_g": med["PSA10"].max().round(3),
            "pct_cells_pga_gt_0.1g": round(100 * (med["PGA"] > 0.1).mean(), 1),
            "pct_cells_pga_gt_0.3g": round(100 * (med["PGA"] > 0.3).mean(), 1),
        })
        print(f"event {ev.event_id} {ev.name}: {duration} duration, max SA(1.0s) {med['PSA10'].max():.2f} g")

    fp = pd.concat(footprint).sort_values(["event_id", "areaperil_id"])
    fp.to_csv(MODEL / "footprint.csv", index=False)
    (MODEL / "areaperil_grid.json").write_text(json.dumps(grid_meta, indent=2))
    cells.assign(**{f"pga_event_{k}": v.round(4) for k, v in pga.items()}).to_csv(
        OUT / "cell_median_pga.csv", index=False)
    cells.assign(**{k: v.round(4) for k, v in sa.items()}).to_csv(OUT / "cell_median_sa.csv", index=False)
    pd.DataFrame(summary).to_csv(OUT / "event_summary.csv", index=False)
    print(pd.DataFrame(summary).to_string(index=False))
    print(f"footprint: {len(fp):,} rows over {grid_meta['n_rows'] * grid_meta['n_cols']:,} cells")


if __name__ == "__main__":
    main()
