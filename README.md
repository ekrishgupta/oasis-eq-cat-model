# Oasis LMF Earthquake Cat Model — Los Angeles

A scenario and probabilistic earthquake catastrophe model for Los Angeles, built on the
open-source [Oasis LMF](https://oasislmf.org) platform.

**Hazard** (USGS ShakeMaps) + **Vulnerability** (FEMA Hazus damage functions) + **Exposure**
(Microsoft building footprints) → **Loss**

## Deliverables

- Loss per historical scenario, one per magnitude band (M5.9 / 6.7 / 6.9 / 7.1 / 7.8)
- Exceedance probability (EP) curve
- VaR at 1-in-100, 1-in-200 and 1-in-250 years
- P(annual loss > $50B in LA)

## Results

![Results](outputs/results/results.png)

| AAL | VaR 1-in-100 | VaR 1-in-200 | VaR 1-in-250 | P(> $50B event in a year) |
|---|---|---|---|---|
| $9.3B | $155B | $185B | $186B | 6.1% (about 1-in-16) |

Ground-up building loss, 2.42M LA County buildings, $3.35T replacement value. See
[docs/step5_results.md](docs/step5_results.md) for validation, limitations, a
[sensitivity analysis](outputs/sensitivity/tornado.png) and a comparison with published
FEMA, vendor and USGS estimates.

## Steps

| # | Step | Status | Code |
|---|------|--------|------|
| 1 | Docker + Oasis platform on EC2 | Done (platform 2.5 running) | [`scripts/step1_setup_oasis.sh`](scripts/step1_setup_oasis.sh) |
| 2 | Vulnerability: Hazus capacity spectrum method | Done | [`docs/step2_vulnerability.md`](docs/step2_vulnerability.md) |
| 3 | Hazard: USGS ShakeMaps → Oasis footprints | Done | [`docs/step3_hazard.md`](docs/step3_hazard.md) |
| 4 | Exposure: Microsoft footprints (LA County) → OED location file | Done | [`docs/step4_exposure.md`](docs/step4_exposure.md) |
| 5 | Run scenarios, attach UCERF3 rates → EP / VaR | Done | [`docs/step5_results.md`](docs/step5_results.md) |

## Data

| Data | Where |
|---|---|
| Code, docs, charts, result tables | This repo |
| Oasis model files (vulnerability, footprint, events, occurrence) | `model_data/` in this repo |
| OED exposure (2.42M buildings) and per-building table | [Release v1.0](https://github.com/ekrishgupta/oasis-eq-cat-model/releases/tag/v1.0) assets (too large for git) |
| Raw ShakeMaps, Microsoft footprint tiles, Census boundary | Third-party; re-downloaded by `scripts/fetch_shakemaps.py` and `scripts/fetch_buildings.py` |

## Layout

```
scripts/   setup and pipeline scripts
docs/      write-ups of each step
data/      raw/ and interim/ are git-ignored; small model files are committed
```
