# Step 5 — Run the model: scenario losses, EP curve, VaR, P(loss > \$50B)

![Results](../outputs/results/results.png)

## Headline numbers

Ground-up **building** loss (structure plus nonstructural components; no contents, business
interruption, fire following, or ground failure) for 2.42M LA County buildings worth \$3.35T,
from the 10-event model run on the Oasis Docker platform (2026-10-15).

| Metric | Value |
|---|---|
| Average annual loss (AAL) | **\$11.7B** |
| VaR 1-in-100 (OEP) | **\$82B**, on a step between \$80B and \$158B (see below) |
| VaR 1-in-200 (OEP) | **\$185B** |
| VaR 1-in-250 (OEP) | **\$186B** |
| P(an event costs > \$50B in a year) | **6.1%** (about 1-in-16 years); 6.1% from the simulated catalogue too |
| P(total annual loss > \$50B) | 7.3% |

### Loss by earthquake

One event per magnitude band, M4.5 to M7.7.

| Mw | Event | Mean loss | % of value | Return period of its band | AAL contribution |
|---|---|---|---|---|---|
| 4.8 | 2002 Yorba Linda | \$0.004B | 0.0001% | 0.75 yr | \$0.005B |
| 5.4 | 2008 Chino Hills | \$3.1B | 0.09% | 2.6 yr | \$1.2B |
| 5.9 | 1987 Whittier Narrows | \$45B | 1.4% | 8.5 yr | \$5.3B |
| 6.4 | 1933 Long Beach | \$59B | 1.7% | 27 yr | \$2.2B |
| 6.6 | 1971 San Fernando | \$79B | 2.3% | 105 yr | \$0.7B |
| 6.7 | 1994 Northridge | \$158B | 4.7% | 233 yr | \$0.7B |
| 6.8 | Raymond–Hollywood fault (USGS scenario) | \$186B | 5.6% | 175 yr | \$1.1B |
| 7.1 | 2019 Ridgecrest | \$0.3B | 0.01% | 166 yr | \$0.002B |
| 7.5 | 1952 Kern County | \$7B | 0.2% | 204 yr | \$0.03B |
| 7.7 | Southern San Andreas ShakeOut (USGS scenario) | \$80B | 2.4% | 150 yr | \$0.5B |

**Distance beats magnitude.** The M6.8 scenario under Hollywood costs more than twice as much as
the M7.7 San Andreas rupture 50 km away, and the M7.1 Ridgecrest quake costs almost nothing.
**Frequent moderate quakes drive the average:** Whittier-type events alone are almost half the AAL.

### Why the 1-in-100 sits on a step

The EP curve from 10 events is a staircase. The two largest events, Raymond–Hollywood (\$186B)
and Northridge (\$158B), have a combined annual rate of 0.0100, almost exactly 1-in-100. So
losses of \$158B or more come once in about 100.5 years, and the 1-in-100 lands on the next step
down: about \$80B, the ShakeOut and San Fernando level. The 8-event run's simulated years
happened to put it at \$155B. Quote it as **between \$80B and \$158B**; only a denser event set
would pin it down. The 1-in-200 and 1-in-250 are both the Raymond–Hollywood step.

## How the run works

1. **Keys lookup** (`model/lookup.py`) gives every OED location its 1 km hazard cell and its
   Hazus class × design-level vulnerability function. All 2,422,140 buildings matched.
2. **Oasis on the Docker platform** (`scripts/run_platform.py`) uploads the exposure, generates
   inputs on the workers (7 min), and runs `gulmc` ground-up loss with 10 samples per building
   and event (10 min).
3. **Catalogue.** UCERF3 LA-region rates per band, simulated over 100,000 Poisson years:
   190,975 occurrences, 1.91 per year (`model_data/occurrence_lt.csv`).
4. **ORD outputs.** Event loss tables (ELT), period loss and AAL (ALT), and exceedance tables
   (EPT: OEP/AEP, full uncertainty), turned into deliverables by `scripts/analyze_results.py`.

**OEP vs AEP.** OEP is the chance the *largest single event* in a year exceeds a loss; AEP is
the chance the *sum of all events* in a year does. They're close except where frequent
moderate events add up, which is why the AEP 1-in-100 is \$155B.

**VaR.** The 1-in-200 VaR is the loss with a 0.5% annual chance of being exceeded; it is the
standard solvency (Solvency II) measure.

## Validation, sensitivity and limitations

These are covered in the full report:
- **Comparison with FEMA, vendor and USGS estimates**, including the Chino Hills and Yorba Linda
  checks: [REPORT §9](REPORT.md#9-validation). The tail and large scenarios are in range; AAL
  is about 4× FEMA's.
- **Sensitivity of each result to each assumption** (tornado chart):
  [REPORT §8](REPORT.md#8-how-firm-are-the-results-sensitivity).
- **Why the AAL is high:** the real catalogue has about 5× fewer M4.5+ quakes near LA than our
  rate attribution assumes: [REPORT §7](REPORT.md#7-frequency-ucerf3-rates-and-the-simulated-catalogue).
- **Full risk and uncertainty register:** [REPORT §13](REPORT.md#13-risks-and-uncertainties-register).

## Reproduce (on EC2, in Docker)

```bash
bash scripts/docker_pipeline.sh            # build -> worker -> run -> analyze
bash scripts/docker_pipeline.sh analyze    # just recompute deliverables, charts, sensitivity
```

`outputs/oasis_run` holds the platform run (`platform_run.json` records the analysis id and
timings). `outputs/oasis_run_mdk` holds the earlier 8-event MDK run.
