"""Extract the Hazus v6.1 PGA-based building fragilities and repair-cost ratios.

Source: SimCenter Damage & Loss Model Library (`simcenter-dlml`, ships with pelicun),
folder seismic/building/portfolio/Hazus v6.1. We keep only the "LF" (lumped fragility)
rows: whole-building fragility curves with Peak Ground Acceleration as the demand, which
is what a USGS ShakeMap gives us. Also writes the structural / nonstructural component
repair-cost ratios used by the capacity spectrum method. Writes small CSVs to data/hazus/ so the build is
reproducible without the library installed.
"""
from pathlib import Path

import dlml
import pandas as pd

SRC = Path(dlml.__file__).parent / "data/seismic/building/portfolio/Hazus v6.1"
OUT = Path(__file__).resolve().parents[1] / "data/hazus"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    frag = pd.read_csv(SRC / "fragility.csv")
    frag = frag[frag["ID"].str.startswith("LF.")]
    assert (frag["Demand-Type"] == "Peak Ground Acceleration").all()
    assert (frag["Demand-Unit"] == "g").all()
    # LF.<structure type>[.<height>].<design level>, e.g. LF.C2.M.HC
    parts = frag["ID"].str.split(".")
    frag.insert(1, "design_level", parts.str[-1])
    frag.insert(1, "building_type", parts.str[1:-1].str.join("."))
    frag.to_csv(OUT / "lf_fragility.csv", index=False)

    cost = pd.read_csv(SRC / "consequence_repair.csv")
    cost = cost[cost["ID"].str.match(r"^LF\..*-Cost$")]
    cost.insert(1, "occupancy", cost["ID"].str.extract(r"^LF\.(.*)-Cost$")[0])
    cost.to_csv(OUT / "lf_repair_cost_ratio.csv", index=False)

    # Component repair-cost ratios used by the capacity spectrum method: structural (STR),
    # drift-sensitive (NSD) and acceleration-sensitive (NSA) nonstructural, by occupancy.
    comp = pd.read_csv(SRC / "consequence_repair.csv")
    comp = comp[comp["ID"].str.match(r"^(STR|NSD|NSA)\.[A-Z0-9]+-Cost$")].drop_duplicates("ID")
    parts = comp["ID"].str.extract(r"^(STR|NSD|NSA)\.(.*)-Cost$")
    comp.insert(1, "component", parts[0])
    comp.insert(2, "occupancy", parts[1])
    comp.to_csv(OUT / "component_repair_cost_ratio.csv", index=False)

    print(f"{len(frag)} fragility rows, {len(cost)} occupancy cost rows, "
          f"{len(comp)} component cost rows -> {OUT}")


if __name__ == "__main__":
    main()
