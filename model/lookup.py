"""Keys lookup for the LA earthquake model.

Oasis calls process_locations() with the OED location table. For every building we return
one key for earthquake shaking (QEQ) on the buildings coverage:
  area_peril_id     the 0.01-degree hazard cell containing the building
  vulnerability_id  the Hazus class x design level vulnerability function
The building's class and design level were written to OED Flexi fields by
scripts/build_exposure.py; the cell is recomputed here from latitude/longitude.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from oasislmf.lookup.interface import KeyLookupInterface
from oasislmf.utils.status import OASIS_KEYS_STATUS

BUILDINGS_COVERAGE = 1
PERIL = "QEQ"


class LAEQKeysLookup(KeyLookupInterface):
    interface_version = "1"

    def __init__(self, config, config_dir=None, user_data_dir=None, output_dir=None):
        self.config = config
        model_data = Path(config_dir or ".") / config["model_data_dir"]
        self.grid = json.loads((model_data / "areaperil_grid.json").read_text())
        vdict = pd.read_csv(model_data / "vulnerability_dict.csv")
        self.vuln_ids = {(r.building_type, r.design_level): r.vulnerability_id for r in vdict.itertuples()}

    def process_locations(self, loc_df):
        cols = {c.lower(): c for c in loc_df.columns}
        lat = loc_df[cols["latitude"]].to_numpy(float)
        lon = loc_df[cols["longitude"]].to_numpy(float)
        g = self.grid
        col = np.floor((lon - g["lon_min"]) / g["step"]).astype(int)
        row = np.floor((lat - g["lat_min"]) / g["step"]).astype(int)
        in_grid = (col >= 0) & (col < g["n_cols"]) & (row >= 0) & (row < g["n_rows"])

        classes = zip(loc_df[cols["flexilochazusclass"]], loc_df[cols["flexilocdesignlevel"]])
        vuln = np.array([self.vuln_ids.get(k, -1) for k in classes])
        ok = in_grid & (vuln > 0)

        keys = pd.DataFrame({
            "loc_id": loc_df["loc_id"].to_numpy(),
            "peril_id": PERIL,
            "coverage_type": BUILDINGS_COVERAGE,
            "area_peril_id": np.where(ok, row * g["n_cols"] + col + 1, -1),
            "vulnerability_id": np.where(ok, vuln, -1),
            "status": np.where(ok, OASIS_KEYS_STATUS["success"]["id"], OASIS_KEYS_STATUS["nomatch"]["id"]),
            "message": np.where(ok, "", np.where(in_grid, "unknown Hazus class", "outside hazard grid")),
        })
        return keys
