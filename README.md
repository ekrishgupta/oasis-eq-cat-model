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

## Steps

| # | Step | Status | Code |
|---|------|--------|------|
| 1 | Docker + Oasis platform on EC2 | Done (platform 2.5 running) | [`scripts/step1_setup_oasis.sh`](scripts/step1_setup_oasis.sh) |
| 2 | Vulnerability from Hazus fragility curves | Done | [`docs/step2_vulnerability.md`](docs/step2_vulnerability.md) |
| 3 | Hazard: USGS ShakeMaps → Oasis footprints | — | |
| 4 | Exposure: Microsoft footprints (LA County) → OED location file | — | |
| 5 | Run scenarios, attach annual rates → EP / VaR | — | |

## Layout

```
scripts/   setup and pipeline scripts
docs/      write-ups of each step
data/      raw/ and interim/ are git-ignored; small model files are committed
```
