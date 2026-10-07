"""Convert USGS ShakeMaps into an Oasis hazard footprint for Los Angeles County.

Model grid: a regular 0.01-degree (~1 km) lon/lat grid over LA County. Each cell is one Oasis
areaperil_id = row * n_cols + col + 1, counted from the south-west corner.

For each event and cell we take the ShakeMap median PGA (grid.xml, %g -> g) and its
uncertainty sigma (uncertainty.xml STDPGA, ln units), interpolated to the cell centre. The
footprint stores the probability that the cell's PGA falls in each intensity bin:

    P(bin i) = Phi((ln to_i - ln median) / sigma) - Phi((ln from_i - ln median) / sigma)

which is the lognormal ground-motion distribution discretised onto the same PGA bins the
vulnerability functions use.

Inputs:  data/events.csv, data/raw/shakemaps/<usgs_id>/{grid,uncertainty}.xml,
         model_data/intensity_bin_dict.csv
Outputs: model_data/footprint.csv, model_data/areaperil_grid.json,
         outputs/hazard/cell_median_pga.csv, outputs/hazard/event_summary.csv
"""
import io
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.interpolate import RegularGridInterpolator
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/shakemaps"
MODEL = ROOT / "model_data"
OUT = ROOT / "outputs/hazard"

# LA County mainland bounding box (excludes Catalina and San Clemente islands).
GRID = {"lon_min": -118.95, "lat_min": 33.70, "lon_max": -117.65, "lat_max": 34.83, "step": 0.01}
MIN_MEDIAN_PGA_G = 0.01   # cells below this get no footprint rows (no damage possible)
MIN_SIGMA = 0.05          # floor to avoid a degenerate distribution at recording stations
MIN_PROB = 1e-5           # drop negligible bin probabilities, then renormalise


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


def bin_probabilities(median: np.ndarray, sigma: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """Lognormal mass per intensity bin; edges has n_bins + 1 entries starting at 0."""
    with np.errstate(divide="ignore"):
        z = (np.log(edges)[None, :] - np.log(median)[:, None]) / sigma[:, None]
    cdf = norm.cdf(z)
    cdf[:, -1] = 1.0  # top bin is open-ended
    return np.diff(cdf, axis=1)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    events = pd.read_csv(ROOT / "data/events.csv")
    ibins = pd.read_csv(MODEL / "intensity_bin_dict.csv")
    edges = np.append(ibins["bin_from"].to_numpy(), ibins["bin_to"].iloc[-1])
    cells, grid_meta = model_grid()
    pts = cells[["lat", "lon"]].to_numpy()

    footprint, medians, summary = [], {}, []
    for ev in events.itertuples():
        grid_df, spec = read_shakemap_xml(RAW / ev.usgs_id / "grid.xml")
        unc_df, unc_spec = read_shakemap_xml(RAW / ev.usgs_id / "uncertainty.xml")
        median = to_interpolator(grid_df, spec, "PGA")(pts) / 100.0  # %g -> g
        sigma = to_interpolator(unc_df, unc_spec, "STDPGA")(pts)
        if np.isnan(median).any():
            raise ValueError(f"{ev.usgs_id}: ShakeMap does not cover the whole LA grid")
        sigma = np.maximum(np.nan_to_num(sigma, nan=0.6), MIN_SIGMA)
        medians[ev.event_id] = median

        keep = median >= MIN_MEDIAN_PGA_G
        probs = bin_probabilities(median[keep], sigma[keep], edges)
        probs[probs < MIN_PROB] = 0.0
        probs /= probs.sum(axis=1, keepdims=True)
        cell_idx, bin_idx = np.nonzero(probs)
        footprint.append(pd.DataFrame({
            "event_id": ev.event_id,
            "areaperil_id": cells["areaperil_id"].to_numpy()[keep][cell_idx],
            "intensity_bin_id": ibins["bin_index"].to_numpy()[bin_idx],
            "probability": probs[cell_idx, bin_idx],
        }))
        summary.append({
            "event_id": ev.event_id, "name": ev.name, "magnitude": ev.magnitude,
            "max_pga_g": median.max().round(3), "mean_pga_g": median.mean().round(3),
            "pct_cells_pga_gt_0.1g": round(100 * (median > 0.1).mean(), 1),
            "pct_cells_pga_gt_0.3g": round(100 * (median > 0.3).mean(), 1),
            "median_sigma": round(float(np.median(sigma)), 2),
        })
        print(f"event {ev.event_id} {ev.name}: max PGA {median.max():.2f} g, "
              f"{keep.sum():,} cells, {len(footprint[-1]):,} rows")

    fp = pd.concat(footprint).sort_values(["event_id", "areaperil_id", "intensity_bin_id"])
    fp.to_csv(MODEL / "footprint.csv", index=False, float_format="%.6e")
    (MODEL / "areaperil_grid.json").write_text(json.dumps(grid_meta, indent=2))
    cells.assign(**{f"pga_event_{k}": v.round(4) for k, v in medians.items()}).to_csv(
        OUT / "cell_median_pga.csv", index=False)
    pd.DataFrame(summary).to_csv(OUT / "event_summary.csv", index=False)
    print(pd.DataFrame(summary).to_string(index=False))
    print(f"footprint: {len(fp):,} rows over {grid_meta['n_rows'] * grid_meta['n_cols']:,} cells")


if __name__ == "__main__":
    main()
