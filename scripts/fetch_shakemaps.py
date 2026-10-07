"""Download the USGS ShakeMap grid.xml and uncertainty.xml for every event in data/events.csv.

Historical events come from the ComCat event service, scenarios from the scenario service.
Each grid.xml is a regular lon/lat grid of ground-motion values (PGA in %g, plus PGV, MMI,
spectral accelerations); uncertainty.xml holds the matching standard deviations (ln units),
e.g. STDPGA. Saved to data/raw/shakemaps/<usgs_id>/.
"""
import json
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/shakemaps"
SERVICE = {
    "event": "https://earthquake.usgs.gov/fdsnws/event/1/query?eventid={}&format=geojson",
    "scenario": "https://earthquake.usgs.gov/fdsnws/scenario/1/query?eventid={}&format=geojson",
}
PRODUCT = {"event": "shakemap", "scenario": "shakemap-scenario"}
FILES = ("grid.xml", "uncertainty.xml")


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def main() -> None:
    events = pd.read_csv(ROOT / "data/events.csv")
    for ev in events.itertuples():
        folder = RAW / ev.usgs_id
        if all((folder / f).exists() for f in FILES):
            print(f"{ev.usgs_id}: cached")
            continue
        detail = get_json(SERVICE[ev.source].format(ev.usgs_id))
        # The preferred (first) shakemap product is the authoritative version.
        product = detail["properties"]["products"][PRODUCT[ev.source]][0]
        folder.mkdir(parents=True, exist_ok=True)
        urls = {f: product["contents"][f"download/{f}"]["url"] for f in FILES}
        for f, url in urls.items():
            urllib.request.urlretrieve(url, folder / f)
        (folder / "product.json").write_text(json.dumps(
            {k: product[k] for k in ("source", "code", "updateTime")} | {"urls": urls}, indent=2))
        size = sum((folder / f).stat().st_size for f in FILES) / 1e6
        print(f"{ev.usgs_id}: {size:.1f} MB from {product['source']}")


if __name__ == "__main__":
    main()
