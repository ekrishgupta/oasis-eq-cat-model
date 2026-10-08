"""Extract the Hazus capacity-spectrum-method tables from the Hazus 6.1 Earthquake Model
Technical Manual (FEMA, 2024) into CSVs under data/hazus/csm/.

The manual is a public-domain FEMA PDF; download it from
https://www.fema.gov/flood-maps/tools-resources/flood-map-products/hazus/user-technical-manuals
and pass its path:  python scripts/extract_hazus_csm_tables.py <manual.pdf>

Tables extracted (design levels HC, MC, LC, PC):
  capacity.csv          Tables 5-12..5-15  yield (Dy in, Ay g) and ultimate (Du in, Au g) points
  building_props.csv    Table 5-8          roof height, elastic period Te, modal factors
  fragility_str.csv     Tables 5-19..5-22  structural damage: median Sd (in) and beta per state
  fragility_nsd.csv     Tables 5-24..5-27  drift-sensitive nonstructural: median Sd (in), beta
  fragility_nsa.csv     Tables 5-31..5-34  acceleration-sensitive nonstructural: median A (g), beta
  kappa.csv             Table 5-42         degradation factor by design level and duration
"""
import re
import sys
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/hazus/csm"
LEVELS = ["HC", "MC", "LC", "PC"]
TYPE = r"(W1|W2|S1[LMH]|S2[LMH]|S3|S4[LMH]|S5[LMH]|C1[LMH]|C2[LMH]|C3[LMH]|PC1|PC2[LMH]|RM1[LM]|RM2[LMH]|URM[LM]|MH)"
NUM = r"-?\d[\d,]*\.?\d*"
STATES = ["slight", "moderate", "extensive", "complete"]


def table_block(lines: list[str], title_prefix: str) -> list[str]:
    """Lines from the body occurrence of a table title up to the next table title."""
    starts = [i for i, l in enumerate(lines) if l.startswith(title_prefix)]
    start = starts[-1]  # the first match is the list of tables at the front of the manual
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"^Table \d+-\d+", lines[i])), len(lines))
    return lines[start:end]


def rows(block: list[str], n_values: int) -> list[tuple[str, list[float]]]:
    """Rows that start with a building type label and end with n_values numbers."""
    out = []
    for line in block:
        line = line.replace("*", "").strip()
        m = re.match(rf"^(?:\d+\s+)?{TYPE}\s+(.*)$", line)
        if not m:
            continue
        nums = [float(x.replace(",", "")) for x in re.findall(NUM, m.group(2))]
        if len(nums) >= n_values:
            out.append((m.group(1), nums[-n_values:]))
    return out


def fragility(lines, titles, value_name):
    recs = []
    for level, title in zip(LEVELS, titles):
        for btype, v in rows(table_block(lines, title), 8):
            rec = {"building_type": btype, "design_level": level}
            for k, s in enumerate(STATES):
                rec[f"{s}_median_{value_name}"], rec[f"{s}_beta"] = v[2 * k], v[2 * k + 1]
            recs.append(rec)
    return pd.DataFrame(recs)


def main(pdf_path: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    text = "\n".join(p.extract_text() or "" for p in PdfReader(pdf_path).pages)
    lines = [l.strip() for l in text.splitlines()]

    cap = []
    for level, t in zip(LEVELS, ["Table 5-12 ", "Table 5-13 ", "Table 5-14 ", "Table 5-15 "]):
        for btype, (dy, ay, du, au) in rows(table_block(lines, t), 4):
            cap.append({"building_type": btype, "design_level": level, "Dy_in": dy, "Ay_g": ay, "Du_in": du, "Au_g": au})
    pd.DataFrame(cap).to_csv(OUT / "capacity.csv", index=False)

    props = [{"building_type": b, "roof_height_ft": v[0], "Te_s": v[1], "alpha1": v[2], "alpha2": v[3]}
             for b, v in rows(table_block(lines, "Table 5-8 "), 6)]
    pd.DataFrame(props).to_csv(OUT / "building_props.csv", index=False)

    fragility(lines, ["Table 5-19 ", "Table 5-20 ", "Table 5-21 ", "Table 5-22 "], "sd_in").to_csv(
        OUT / "fragility_str.csv", index=False)
    fragility(lines, ["Table 5-24 ", "Table 5-25 ", "Table 5-26 ", "Table 5-27 "], "sd_in").to_csv(
        OUT / "fragility_nsd.csv", index=False)
    fragility(lines, ["Table 5-31 ", "Table 5-32 ", "Table 5-33 ", "Table 5-34 "], "a_g").to_csv(
        OUT / "fragility_nsa.csv", index=False)

    kap = []
    for btype, v in rows(table_block(lines, "Table 5-42 "), 12):
        for i, level in enumerate(LEVELS):
            kap.append({"building_type": btype, "design_level": level,
                        "short": v[3 * i], "moderate": v[3 * i + 1], "long": v[3 * i + 2]})
    pd.DataFrame(kap).to_csv(OUT / "kappa.csv", index=False)

    for f in sorted(OUT.glob("*.csv")):
        df = pd.read_csv(f)
        print(f"{f.name}: {len(df)} rows")


if __name__ == "__main__":
    main(sys.argv[1])
