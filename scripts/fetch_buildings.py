"""Download Microsoft building footprints and the LA County boundary.

Microsoft Global ML Building Footprints are published as gzipped GeoJSON-lines tiles keyed
by Bing Maps quadkey (level 9 for the US, ~0.7 degrees across). Each record is a building
polygon with an estimated height in metres (-1 if unknown) and a detection confidence.
We download only the tiles that intersect the LA hazard grid.

The county boundary is the US Census 2023 cartographic boundary file (1:500k).

Outputs: data/raw/buildings/<quadkey>.geojsonl.gz, data/raw/boundaries/cb_2023_us_county_500k.zip
"""
import json
import math
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"
LINKS = "https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv"
COUNTIES = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_500k.zip"
QUADKEY_LEVEL = 9


def tile_xy(lon: float, lat: float, z: int) -> tuple[int, int]:
    """Web-Mercator tile containing (lon, lat) at zoom z."""
    s = math.sin(math.radians(lat))
    n = 2 ** z
    return int((lon + 180) / 360 * n), int((0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n)


def quadkey(x: int, y: int, z: int) -> str:
    return "".join(str(((x >> i) & 1) + 2 * ((y >> i) & 1)) for i in range(z - 1, -1, -1))


def main() -> None:
    grid = json.loads((ROOT / "model_data/areaperil_grid.json").read_text())
    x0, y0 = tile_xy(grid["lon_min"], grid["lat_max"], QUADKEY_LEVEL)
    x1, y1 = tile_xy(grid["lon_max"], grid["lat_min"], QUADKEY_LEVEL)
    wanted = {quadkey(x, y, QUADKEY_LEVEL) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}

    with urllib.request.urlopen(LINKS, timeout=120) as r:
        rows = [line.split(",") for line in r.read().decode().splitlines()[1:]]
    urls = {qk: url for region, qk, url, *_ in rows if region == "UnitedStates" and qk in wanted}

    out = RAW / "buildings"
    out.mkdir(parents=True, exist_ok=True)
    for qk, url in sorted(urls.items()):
        path = out / f"{qk}.geojsonl.gz"
        if not path.exists():
            urllib.request.urlretrieve(url, path)
        print(f"{qk}: {path.stat().st_size / 1e6:.1f} MB")

    bdir = RAW / "boundaries"
    bdir.mkdir(parents=True, exist_ok=True)
    counties = bdir / Path(COUNTIES).name
    if not counties.exists():
        urllib.request.urlretrieve(COUNTIES, counties)
    print(f"{counties.name}: {counties.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
