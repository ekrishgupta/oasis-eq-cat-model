# Step 4 — Exposure from Microsoft building footprints

**Question answered:** which buildings are in Los Angeles, where are they, what are they
made of, and what would it cost to rebuild them?

![Exposure map](../outputs/exposure/exposure_map.png)

## Source

**Microsoft Global ML Building Footprints.** These are building outlines extracted by a
neural network from aerial imagery, with an **estimated height** for most buildings.
They're published as gzipped GeoJSON-lines tiles indexed by Bing Maps quadkey. Nine
level-9 tiles (about 440 MB) cover the LA hazard grid. The older US-only release
(`usbuildings-v2`) is no longer publicly downloadable.

County boundary: US Census 2023 cartographic boundary file. We keep **mainland LA County**,
which excludes Catalina and San Clemente islands.

## Pipeline (`scripts/build_exposure.py`)

| Step | Rule | Why |
|---|---|---|
| Clip | Building centroid inside LA County and inside the hazard grid | One portfolio, every building has hazard |
| Footprint area | Polygon area in California Albers (EPSG:3310), m² → sqft | Equal-area projection, so areas are true |
| Filter | Drop footprints under 400 sqft | Sheds and detached garages |
| Floors | round(height ÷ 3.3 m), minimum 1; 1 if height unknown (4% of buildings) | A typical storey is about 3–3.5 m |
| Hazus class | Size rules, below | No year, use or material data in the footprints |
| Design level | Random draw: 15% pre-code, 50% moderate, 35% high code | Approximate LA age mix: pre-1941 / 1941–75 / post-1975 |
| Value | footprint × floors × replacement cost per sqft | Building replacement cost, not market value |
| Hazard cell | 0.01° cell containing the centroid → `areaperil_id` | Links each building to the footprint |

**Building class rules**, applied in order with later rules winning:

| Condition | Class | Interpretation | $/sqft |
|---|---|---|---|
| Default | W2 | Mid-size wood (apartments, small commercial) | 325 |
| Footprint < 3,000 sqft and ≤ 2 floors | W1 | Single-family wood house | 350 |
| Footprint ≥ 15,000 sqft and ≤ 2 floors | PC1 | Tilt-up warehouse or big-box store | 175 |
| ≥ 3 floors, footprint ≥ 3,000 sqft | C2.L | Concrete shear wall, 3 storeys | 375 |
| ≥ 4 floors, footprint ≥ 3,000 sqft | C2.M | Concrete shear wall, 4–7 storeys | 400 |
| ≥ 8 floors | S1.H | Steel moment-frame tower | 475 |

## Result

**2,422,140 buildings, $3.35 trillion building replacement value.**

| Class | Buildings | Avg footprint (sqft) | Avg floors | Value ($bn) | Share |
|---|---|---|---|---|---|
| W1 | 1,958,462 | 1,703 | 1.15 | 1,366 | 41% |
| W2 | 410,223 | 4,665 | 1.35 | 861 | 26% |
| C2.L | 16,934 | 24,800 | 3.0 | 472 | 14% |
| PC1 | 31,165 | 39,208 | 1.74 | 382 | 11% |
| C2.M | 4,979 | 26,501 | 4.6 | 244 | 7% |
| S1.H | 377 | 17,914 | 8.6 | 28 | 1% |

Sanity checks:
- About 1.96M houses, against roughly 1.7–1.8M single-family homes in LA County. Ours also
  includes some small commercial buildings and large garages.
- The average house is about 1,960 sqft of floor area at $350/sqft, a replacement cost of
  about $690k. That's plausible for rebuilding in LA.

## OED location file

`inputs/oed_location_la.csv` (about 200 MB, regenerated rather than committed) follows the
**Open Exposure Data** standard that Oasis reads:

- `Latitude`, `Longitude`, `CountryCode=US`, `LocCurrency=USD`
- `OccupancyCode` and `ConstructionCode`: real OED codes, e.g. 1051 single-family with 5050
  wood frame; 1150 industrial with 5155 tilt-up; 1104 office with 5205 steel moment frame
- `NumberOfStoreys`, `BuildingTIV` (contents and BI set to 0: building damage only)
- `LocPerilsCovered=QEQ`: earthquake shaking only
- `FlexiLocHazusClass`, `FlexiLocDesignLevel`: OED "Flexi" fields carrying our model's
  classification to the keys lookup

## Biggest assumptions (say these out loud)

1. **Building type from size alone.** A 2,000 sqft footprint could be a house or a corner
   shop. Real cat models use the county assessor's parcel data (year built, use, material).
2. **Design level is a random draw.** No building has a known age, so the mix is right in
   aggregate but wrong for any individual building. That's fine for a portfolio, not for
   pricing a single risk.
3. **No unreinforced masonry or non-ductile concrete.** These are LA's most dangerous
   building types, but without year built we can't find them. This likely
   **understates** loss.
4. **Replacement cost per sqft** drives the total value linearly. ±20% on the cost
   assumptions is ±20% on every loss number.
5. **ML heights** can be off for buildings under trees or with unusual roofs.

## Reproduce (on EC2)

```bash
python scripts/fetch_buildings.py   # 9 tiles + county boundary -> data/raw/
python scripts/build_exposure.py    # -> inputs/oed_location_la.csv (~2 min)
python scripts/plot_exposure.py     # -> outputs/exposure/exposure_map.png
```
