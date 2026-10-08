# Step 5 — Run the model: scenario losses, EP curve, VaR, P(loss > $50B)

![Results](../outputs/results/results.png)

## Headline numbers

Ground-up **building** loss (structure plus nonstructural components; no contents, business
interruption, fire following, or ground failure) for 2.42M LA County buildings worth $3.35T.

| Metric | Value |
|---|---|
| Average annual loss (AAL) | **$9.3B** |
| VaR 1-in-100 (OEP) | **$155B** |
| VaR 1-in-200 (OEP) | **$185B** |
| VaR 1-in-250 (OEP) | **$186B** |
| P(an event costs > $50B in a year) | **6.1%** (about 1-in-16 years); 6.2% from the simulated catalogue |
| P(total annual loss > $50B) | 6.6% |

### Loss by earthquake

| Mw | Event | Mean loss | % of value | Return period of its band |
|---|---|---|---|---|
| 5.9 | 1987 Whittier Narrows | $45B | 1.4% | 11 yr |
| 6.4 | 1933 Long Beach | $59B | 1.7% | 27 yr |
| 6.6 | 1971 San Fernando | $79B | 2.3% | 105 yr |
| 6.7 | 1994 Northridge | $158B | 4.7% | 233 yr |
| 6.8 | Raymond–Hollywood fault (USGS scenario) | $186B | 5.6% | 175 yr |
| 7.1 | 2019 Ridgecrest | $0.3B | 0.01% | 166 yr |
| 7.5 | 1952 Kern County | $7B | 0.2% | 204 yr |
| 7.7 | Southern San Andreas ShakeOut (USGS scenario) | $80B | 2.4% | 150 yr |

**Distance beats magnitude.** The M6.8 scenario under Hollywood costs more than twice as
much as the M7.7 San Andreas rupture 50 km away, and the M7.1 Ridgecrest quake costs almost
nothing.

## How the run works

1. **Keys lookup** (`model/lookup.py`). Every OED location gets its 1 km hazard cell
   (`areaperil_id`) and its Hazus class × design-level vulnerability function. All
   2,422,140 buildings matched, with 0 errors.
2. **Oasis ground-up loss** (`gulmc`). For each event and building: look up the cell's
   intensity bin, which is (SA 0.3 s, SA 1.0 s, duration). Sample 10 damage ratios from the
   vulnerability distribution and multiply by building value. This takes 3.5 minutes on
   2 vCPUs.
3. **Catalogue.** Each event's annual rate comes from UCERF3 LA-region recurrence (Step 3
   rates), simulated over 100,000 Poisson years (`model_data/occurrence_lt.csv`).
4. **ORD outputs.** Event loss tables (ELT), period loss and AAL (ALT), and exceedance
   probability tables (EPT: OEP/AEP, full uncertainty). The results are computed by
   `scripts/analyze_results.py`.

**OEP vs AEP.** OEP is the chance that the *largest single event* in a year exceeds a loss;
AEP is the chance that the *sum of all events* in a year exceeds it. With at most a few
damaging quakes per year, they're nearly equal here.

**VaR.** The 1-in-200 VaR is the loss with a 0.5% annual chance of being exceeded; it is
the standard solvency (Solvency II) measure.

## Validation

The Oasis engine was checked independently: summing TIV × P(intensity) × MDR in pandas
reproduces every Oasis event mean to within 0.5%.

| Event | Model | Benchmark (2026 $, approx.) | Source |
|---|---|---|---|
| M7.7 ShakeOut | $80B | ~$70B | USGS ShakeOut Scenario: $46B shaking damage to buildings and contents (2008 $), all of Southern California |
| M6.7 Northridge | $158B | $90–155B total economic (2014 $) | AIR/RMS/EQECAT panel, PEER Northridge20 (2014), shaking + fire, all lines |
| M5.9 Whittier Narrows | $45B | ~$1B | $358M property damage (1987 $) |

### What changed between model versions

| | v1: Hazus PGA ("equivalent-PGA") fragility | v2: Hazus capacity spectrum (current) |
|---|---|---|
| Whittier Narrows | $108B | $45B |
| Northridge | $299B | $158B |
| ShakeOut | $82B | $80B |
| AAL | $19.8B | $9.3B |

Two things changed together. (a) v1 spread each cell's PGA over a lognormal distribution
on top of the Hazus fragility betas, double-counting ground-motion variability. Removing
that alone takes Whittier from $108B to $75B and Northridge from $299B to $255B. (b) The
vulnerability method moved from the PGA shortcut, which is calibrated for large events, to
the full capacity spectrum method, which sees each event's spectrum and duration. That
takes Whittier to $45B and Northridge to $158B, about 1.6× lower again.

## How firm are the numbers? Sensitivity

![Tornado](../outputs/sensitivity/tornado.png)

This doesn't change the results; the baseline *is* our result. Each bar changes one
assumption and shows how far AAL, the 1-in-200 VaR and P(> $50B) move
(`scripts/sensitivity.py`). For speed it recomputes mean losses directly rather than
re-running Oasis, and its baseline reproduces the Oasis event means to within 1%. It uses
mean losses, so its 1-in-200 is $187B against Oasis's $185B with sampling.

| Assumption | Range tested | AAL | 1-in-200 VaR | P(> $50B) |
|---|---|---|---|---|
| **Baseline** | | **$9.3B** | **$187B** | **6.1%** |
| Rate attribution | ½ or ¼ of band events hit the scenario location | $4.6B / $2.3B | $79B / $78B | 3.1% / 1.6% |
| Fragility dispersion | Hazus β × 0.8 / × 1.2 | $6.5B / $13.3B | $146B / $238B | 2.6% / 14.1% |
| Replacement cost | −25% / +25% | $7.0B / $11.6B | $140B / $234B | 2.6% / 14.1% |
| Design-level mix | Newer (5/35/60% PC/MC/HC) / older (30/50/20%) | $8.1B / $10.6B | $161B / $216B | 2.6% / 14.1% |
| Shaking duration | All moderate / all long | $9.2B / $10.6B | $187B / $229B | 6.1% / 6.1% |
| Elastic damping | Wood 10% / steel 7%, concrete 10% | $10.8B / $8.6B | $211B / $178B | 14.1% / 6.1% |
| Capacity curve shape | Bilinear instead of elliptical | $9.4B | $197B | 6.1% |

What this says:
- **Rate attribution is the biggest lever.** It's an assumption about *where* band events
  happen, not about buildings. If only half of LA-region quakes in each band hit as close
  as the historical one, AAL and P(> $50B) halve and the 1-in-200 falls to $79B.
- **Among vulnerability inputs, fragility dispersion matters most**, as much as a ±25%
  change in building values. The two choices that are mine rather than Hazus's (curve
  shape) or that sit inside Hazus's published ranges (damping) move results by 10% or less.
- **P(> $50B) is a cliff, not a slope.** Whittier Narrows ($46B) and Long Beach ($58B) sit
  either side of $50B, so small changes flip the probability between about 2.6% and 14%.
  A $50B threshold sits right where the event set is thin; with a dense stochastic catalogue
  the probability would move smoothly.

## Comparison with published estimates

| Measure | Ours (building only, 2026 $) | Published | Source |
|---|---|---|---|
| LA County AAL | $9.3B | $2.68B (Hazus; buildings, contents, inventory and income loss; 2022 $). Building-only is roughly $1.7B using California's 64% building share | [FEMA P-366, 2023](https://www.fema.gov/sites/default/files/documents/fema_p-366-hazus-estimated-annualized-earthquake-losses-united-states.pdf) |
| LA County AAL | $9.3B | $2.97B building expected annual loss | [FEMA National Risk Index](https://hazards.fema.gov/nri/) (Dec 2025) |
| LA County 1-in-100 | $155B | $72.3B (Hazus; county-wide uniform-hazard shaking) | FEMA P-366, Table C-3 |
| LA County 1-in-250 | $186B | $163.3B (same) | FEMA P-366, Table C-3 |
| LA Basin 1-in-100 / 1-in-250 | $155B / $186B | $137–173B / $215–263B (5 counties, total economic) | [AIR/RMS/EQECAT panel, PEER Northridge20, 2014](https://northridge20.peer.berkeley.edu/wp-content/uploads/2010/10/DirectImpacts_Tillman.pdf) |
| Northridge repeat | $158B | $90–155B economic; $12–24B insured | Same panel; [RMS via Carrier Management, 2014](https://carriermanagement.com/news/2014/01/20/117897.htm) |
| ShakeOut M7.8 | $80B | $46B shaking damage to buildings and contents (about $70B in 2026 $); $191B total incl. fire and business interruption | [Porter et al. 2011](https://pubs.usgs.gov/publication/70034995) |
| Puente Hills thrust | (Raymond–Hollywood M6.8: $186B) | $82–252B economic | [Field et al. 2005](https://pubs.usgs.gov/publication/70029508) |

Reading it:
- **Tail (1-in-100 to 1-in-250) and large scenarios are in range.** Our 1-in-100 sits
  inside the vendor panel's range and our 1-in-250 is close to Hazus's. The large events
  fall at or near the top of published ranges.
- **AAL is about 3× published Hazus/NRI figures.** That's consistent with the sensitivity
  results: the rate-attribution assumption puts every band event at the city's doorstep,
  and with only a quarter of band events hitting the city, AAL would be $2.3B. Published
  Hazus AAL also excludes shaking more frequent than 1-in-100, which includes the
  Whittier-type events that drive our AAL.
- **Our curve is flat between 1-in-100 and 1-in-250** while both benchmarks keep rising.
  That's the 8-event catalogue, not the physics.
- **Insured is far below economic.** About 12% of California homeowners carry earthquake
  cover ([CDI 2024](https://www.insurance.ca.gov/0400-news/0200-studies-reports/0300-earthquake-study/upload/EQEXP2024Summary.pdf)),
  so a $150B+ economic event is a $12–24B insured event. The CEA sizes its claims-paying
  capacity ($19.9B) to about a 1-in-390 event.

## Limitations, in order of impact

1. **Rates are conservative.** Each event stands for *every* LA-region quake in its
   magnitude band, as if it struck where the historical one did. Most real ruptures in the
   UCERF3 LA region (about 100 km around LA) are farther from the dense core. This
   inflates P(> $50B) and the AAL, so treat 6% as an upper-end estimate.
2. **Eight events is a thin catalogue.** The EP curve is a staircase and flattens at the
   largest event ($186B), so the 1-in-200 and 1-in-250 VaR are both "the Raymond–Hollywood
   scenario". A production model uses thousands of stochastic ruptures. The next step is
   to sample UCERF3 ruptures and use USGS ground-motion models.
3. **Hazus is conservative for moderate events** (Whittier is about 40× its 1987 benchmark),
   largely from "slight damage" tails across millions of buildings.
4. **Exposure inference.** Building type comes from footprint size and height, and design
   level from a county-wide age mix, because there's no year-built data. Using assessor
   parcel data would sharpen this.
5. **Scope.** Building damage only. Contents, business interruption, fire following,
   liquefaction and landslide are excluded. Ground-up loss means no deductibles or limits.

## Reproduce (on EC2)

```bash
python scripts/build_vulnerability_csm.py   # Hazus CSM vulnerability -> model_data/
python scripts/build_footprint.py           # ShakeMap spectra -> footprint
bash scripts/run_oasis.sh                   # compile binaries + Oasis run (~4 min)
python scripts/analyze_results.py           # -> outputs/results/
python scripts/plot_results.py              # -> outputs/results/results.png
python scripts/sensitivity.py               # -> outputs/sensitivity/ (~1 min, runs locally)
python scripts/plot_sensitivity.py          # -> outputs/sensitivity/tornado.png
```
