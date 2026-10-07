# Step 3 — Hazard from USGS ShakeMaps

**Question answered:** for each earthquake, how hard did the ground shake at each point in
Los Angeles?

![Footprint maps](../outputs/hazard/footprint_maps.png)

## Event set

One event per magnitude band, chosen because each one shakes LA. Where LA has no damaging
historical quake in a band, we use an official USGS scenario.

| ID | Mw | Event | Type | LA max PGA | LA cells > 0.1 g |
|---|---|---|---|---|---|
| 1 | 5.9 | 1987 Whittier Narrows | Historical | 0.40 g | 21% |
| 2 | 6.4 | 1933 Long Beach | Historical (reconstructed) | 0.65 g | 20% |
| 3 | 6.6 | 1971 San Fernando | Historical (reconstructed) | 1.01 g | 60% |
| 4 | 6.7 | 1994 Northridge | Historical | 0.87 g | 71% |
| 5 | 6.8 | Raymond–Hollywood fault | USGS scenario | 0.66 g | 45% |
| 6 | 7.1 | 2019 Ridgecrest | Historical, about 200 km away | 0.06 g | 0% |
| 7 | 7.5 | 1952 Kern County | Historical (reconstructed) | 0.25 g | 15% |
| 8 | 7.7 | Southern San Andreas (ShakeOut) | USGS scenario | 0.68 g | 83% |

The headline lesson is that **magnitude is not loss; distance is**. The M7.1 Ridgecrest
quake barely moves LA (0.06 g at most), while the M5.9 Whittier Narrows quake directly
underneath reaches 0.40 g.

Historical ShakeMaps before about 1990 come from the USGS ShakeMap Atlas. These
reconstruct shaking from the fault model, ground-motion prediction equations and
intensity reports. The configuration is in `data/events.csv`.

## What a ShakeMap is

A regular lon/lat grid, 0.008–0.017° spacing (about 1–2 km), with the median ground motion
at each point: PGA (%g), PGV, MMI and spectral accelerations. A companion
`uncertainty.xml` gives the standard deviation of ln(PGA). Uncertainty is small near
seismic stations and larger far from them, typically σ ≈ 0.4–0.6.

## From ShakeMap to Oasis footprint

1. **Model grid.** A regular 0.01° grid (about 1 km) over mainland LA County, giving
   14,690 cells. Each cell is one Oasis `areaperil_id` (`model_data/areaperil_grid.json`).
   In Step 4, every building is assigned the cell it sits in.
2. **Interpolate.** Bilinear interpolation of median PGA and σ to each cell centre.
3. **Discretise the uncertainty.** An Oasis footprint is not a single number per cell; it
   is a probability distribution over intensity bins. For each cell:

   P(bin i) = Φ((ln to_i − ln median) / σ) − Φ((ln from_i − ln median) / σ)

   This is the lognormal ground-motion distribution, laid on the same 201 PGA bins as
   the vulnerability functions. Oasis then samples both the intensity and the damage.
4. **Trim.** Cells with median PGA below 0.01 g are dropped (no damage is possible), and
   bin probabilities below 10⁻⁵ are removed, with the rest renormalised to sum to 1.

The result is `model_data/footprint.csv`: 6.8 million rows (event, cell, PGA bin,
probability), about 150 MB. It is rebuilt rather than committed.

## Why include the uncertainty

The loss curve is convex in PGA: damage accelerates as shaking rises. So the average loss
over the distribution of PGA is higher than the loss at the median PGA. Ignoring
ground-motion uncertainty would systematically understate loss.

## Simplifications to state when presenting

- Cell-to-cell uncertainty is sampled independently. Real ground-motion errors are
  spatially correlated, so this understates the spread of the portfolio loss around its
  mean. The mean itself is unaffected.
- The 0.01° grid smooths sharp local effects such as basin edges and individual hillsides.
- PGA only. Long-period shaking, which matters for tall buildings in a distant M7.7, is
  not used.

## Reproduce (on EC2)

```bash
python scripts/fetch_shakemaps.py   # ~240 MB of ShakeMap XML -> data/raw/shakemaps/
python scripts/build_footprint.py   # -> model_data/footprint.csv, outputs/hazard/*.csv
python scripts/plot_footprints.py   # -> outputs/hazard/footprint_maps.png
```
