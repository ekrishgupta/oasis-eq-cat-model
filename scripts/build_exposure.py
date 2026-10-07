"""Build the LA County exposure (OED location file) from Microsoft building footprints.

For every building whose centroid lies in mainland LA County:
  footprint area  from the polygon in California Albers (EPSG:3310), in sqft
  floors          from Microsoft's estimated height: round(height / 3.3 m), min 1;
                  1 when height is unknown
  Hazus class     from footprint area and floors (rules in assign_class)
  design level    Hazus seismic code level, drawn from LA's approximate age mix
  value           footprint area x floors x replacement cost per sqft for the class
  areaperil_id    the 0.01-degree hazard grid cell the centroid falls in

Outputs: inputs/oed_location_la.csv (OED), data/interim/la_buildings.parquet,
         outputs/exposure/summary_by_class.csv
"""
import json
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"
FT2_PER_M2 = 10.7639
STOREY_HEIGHT_M = 3.3
MIN_FOOTPRINT_SQFT = 400  # drop sheds and detached garages

# Replacement cost (not market value) per sqft of floor area, LA 2026, building only.
# Round-number assumptions in line with published LA construction-cost ranges; state them
# as assumptions and test sensitivity.
COST_PER_SQFT = {"W1": 350, "W2": 325, "PC1": 175, "C2.L": 375, "C2.M": 400, "S1.H": 475}

# OED codes (ods_tools OED 4.0 spec): occupancy and construction per Hazus class.
OED_CODES = {
    #        OccupancyCode                    ConstructionCode
    "W1":   (1051, 5050),  # single-family dwelling, wood frame
    "W2":   (1052, 5050),  # multi-family dwelling, wood frame
    "PC1":  (1150, 5155),  # general industrial, concrete tilt-up
    "C2.L": (1052, 5152),  # multi-family, RC shear wall
    "C2.M": (1052, 5152),
    "S1.H": (1104, 5205),  # offices, steel moment frame
}

# Approximate LA County building-age mix, mapped to Hazus design levels
# (pre-1941 pre-code, 1941-1975 moderate code, post-1975 high code).
DESIGN_LEVEL_MIX = {"PC": 0.15, "MC": 0.50, "HC": 0.35}
SEED = 20260107


def la_county(grid: dict) -> shapely.Geometry:
    with zipfile.ZipFile(RAW / "boundaries/cb_2023_us_county_500k.zip") as z:
        shp = next(n for n in z.namelist() if n.endswith(".shp"))
    counties = gpd.read_file(f"zip://{RAW / 'boundaries/cb_2023_us_county_500k.zip'}!{shp}")
    county = counties.query("STATEFP == '06' and COUNTYFP == '037'").to_crs(4326).geometry.iloc[0]
    box = shapely.box(grid["lon_min"], grid["lat_min"], grid["lon_max"], grid["lat_max"])
    return county.intersection(box)  # mainland part inside the hazard grid


def read_tiles(grid: dict, county: shapely.Geometry) -> gpd.GeoDataFrame:
    shapely.prepare(county)
    bbox = (grid["lon_min"], grid["lat_min"], grid["lon_max"], grid["lat_max"])
    parts = []
    for path in sorted((RAW / "buildings").glob("*.geojsonl.gz")):
        gdf = pyogrio.read_dataframe(f"/vsigzip/{path}", bbox=bbox)
        if gdf.empty:
            continue
        # Planar centroid in degrees: for a building-sized polygon the error is millimetres.
        c = shapely.centroid(gdf.geometry.values)
        gdf = gdf[shapely.contains_xy(county, shapely.get_x(c), shapely.get_y(c))]
        print(f"{path.name}: {len(gdf):,} buildings in LA County")
        parts.append(gdf[["height", "confidence", "geometry"]])
    return gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=4326)


def assign_class(footprint_sqft: np.ndarray, floors: np.ndarray) -> np.ndarray:
    """Hazus building class from size alone (no age, use or material data available)."""
    cls = np.full(footprint_sqft.shape, "W2", dtype=object)          # mid-size wood apartments
    cls[(footprint_sqft < 3_000) & (floors <= 2)] = "W1"           # houses
    cls[(footprint_sqft >= 15_000) & (floors <= 2)] = "PC1"         # warehouses, big boxes
    cls[(floors >= 3) & (footprint_sqft >= 3_000)] = "C2.L"         # 3-storey concrete
    cls[(floors >= 4) & (footprint_sqft >= 3_000)] = "C2.M"         # 4-7 storey concrete
    cls[floors >= 8] = "S1.H"                                       # towers
    return cls


def main() -> None:
    grid = json.loads((ROOT / "model_data/areaperil_grid.json").read_text())
    county = la_county(grid)
    b = read_tiles(grid, county)

    centroids = shapely.centroid(b.geometry.values)
    b["lon"], b["lat"] = shapely.get_x(centroids).round(6), shapely.get_y(centroids).round(6)
    b["footprint_sqft"] = b.geometry.to_crs(3310).area * FT2_PER_M2
    b = b[b["footprint_sqft"] >= MIN_FOOTPRINT_SQFT].reset_index(drop=True)

    height_known = b["height"] > 0
    b["floors"] = np.where(height_known, np.clip(np.round(b["height"] / STOREY_HEIGHT_M), 1, 80), 1).astype(int)
    b["hazus_class"] = assign_class(b["footprint_sqft"].to_numpy(), b["floors"].to_numpy())
    rng = np.random.default_rng(SEED)
    b["design_level"] = rng.choice(list(DESIGN_LEVEL_MIX), size=len(b), p=list(DESIGN_LEVEL_MIX.values()))
    b["floor_area_sqft"] = b["footprint_sqft"] * b["floors"]
    b["building_tiv"] = (b["floor_area_sqft"] * b["hazus_class"].map(COST_PER_SQFT)).round(-2)

    col = ((b["lon"] - grid["lon_min"]) / grid["step"]).astype(int).clip(0, grid["n_cols"] - 1)
    row = ((b["lat"] - grid["lat_min"]) / grid["step"]).astype(int).clip(0, grid["n_rows"] - 1)
    b["areaperil_id"] = row * grid["n_cols"] + col + 1

    vdict = pd.read_csv(ROOT / "model_data/vulnerability_dict.csv")
    b = b.merge(vdict[["building_type", "design_level", "vulnerability_id"]],
                left_on=["hazus_class", "design_level"], right_on=["building_type", "design_level"],
                how="left", validate="many_to_one").drop(columns="building_type")
    assert b["vulnerability_id"].notna().all()

    occ, cons = zip(*b["hazus_class"].map(OED_CODES))
    oed = pd.DataFrame({
        "PortNumber": 1, "AccNumber": 1, "LocNumber": np.arange(1, len(b) + 1),
        "Latitude": b["lat"], "Longitude": b["lon"], "CountryCode": "US", "AreaCode": "CA",
        "OccupancyCode": occ, "ConstructionCode": cons, "NumberOfStoreys": b["floors"],
        "LocPerilsCovered": "QEQ", "BuildingTIV": b["building_tiv"],
        "ContentsTIV": 0, "BITIV": 0, "OtherTIV": 0, "LocCurrency": "USD",
        # Model-specific attributes for our keys lookup (OED allows Flexi fields).
        "FlexiLocHazusClass": b["hazus_class"], "FlexiLocDesignLevel": b["design_level"],
        "FlexiLocFloorAreaSqft": b["floor_area_sqft"].round(0).astype(int),
    })

    (ROOT / "inputs").mkdir(exist_ok=True)
    (ROOT / "data/interim").mkdir(parents=True, exist_ok=True)
    (ROOT / "outputs/exposure").mkdir(parents=True, exist_ok=True)
    oed.to_csv(ROOT / "inputs/oed_location_la.csv", index=False)
    b.drop(columns="geometry").to_parquet(ROOT / "data/interim/la_buildings.parquet", index=False)

    summary = b.groupby("hazus_class").agg(
        buildings=("building_tiv", "size"), mean_footprint_sqft=("footprint_sqft", "mean"),
        mean_floors=("floors", "mean"), total_tiv_usd_bn=("building_tiv", lambda s: s.sum() / 1e9))
    summary["share_of_tiv"] = summary["total_tiv_usd_bn"] / summary["total_tiv_usd_bn"].sum()
    summary.round(3).to_csv(ROOT / "outputs/exposure/summary_by_class.csv")
    print(summary.round(2).to_string())
    print(f"\n{len(b):,} buildings, total building TIV ${b['building_tiv'].sum() / 1e12:.2f} trillion, "
          f"height known for {height_known.mean():.0%}")


if __name__ == "__main__":
    main()
