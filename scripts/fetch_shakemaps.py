"""Download the USGS ShakeMap grid.xml for every event in data/events.csv.

Historical events come from the ComCat event service, scenarios from the scenario service.
Each grid.xml is a regular lon/lat grid of ground-motion values (PGA in %g, plus PGV, MMI,
spectral accelerations and their uncertainties). Saved to data/raw/shakemaps/<usgs_id>/.
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


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def main() -> None:
    events = pd.read_csv(ROOT / "data/events.csv")
    for ev in events.itertuples():
        out = RAW / ev.usgs_id / "grid.xml"
        if out.exists():
            print(f"{ev.usgs_id}: cached")
            continue
        detail = get_json(SERVICE[ev.source].format(ev.usgs_id))
        # The preferred (first) shakemap product is the authoritative version.
        product = detail["properties"]["products"]["shakemap"][0]
        url = product["contents"]["download/grid.xml"]["url"]
        out.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(url, out)
        (out.parent / "product.json").write_text(json.dumps(
            {k: product[k] for k in ("source", "code", "updateTime")} | {"url": url}, indent=2))
        print(f"{ev.usgs_id}: {out.stat().st_size / 1e6:.1f} MB from {product['source']}")


if __name__ == "__main__":
    main()
