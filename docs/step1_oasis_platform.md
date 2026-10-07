# Step 1 — The Oasis engine

## What Oasis is

Oasis LMF is an open-source loss-modelling framework. It contains no hazard science of its
own: you supply the model files and it does the loss maths and the insurance accounting.

| Oasis term | What it is | In this project |
|---|---|---|
| Footprint | For each event: a probability over intensity bins in each grid cell | USGS ShakeMaps (Step 3) |
| Vulnerability | For each building type: a probability over damage-ratio bins, given an intensity bin | Hazus curves (Step 2) |
| Keys / lookup | Maps each building to its grid cell and vulnerability ID | Custom lookup (Steps 3–4) |
| OED exposure | The standard location file: lat, lon, construction, value | Microsoft footprints (Step 4) |

## The calculation pipeline (ktools)

```
eve → getmodel → gulcalc → fmcalc → summarycalc → eltcalc / leccalc / aalcalc
```

- `eve`: lists the events to run
- `getmodel`: combines footprint and vulnerability into a damage distribution per building
- `gulcalc`: samples ground-up loss per building
- `fmcalc`: applies policy terms (deductibles, limits)
- `summarycalc`: aggregates losses
- `eltcalc`: event loss table → loss per scenario
- `leccalc`: loss exceedance curves → EP curve, VaR, P(loss > $50B)
- `aalcalc`: average annual loss

In OasisLMF 2.5 most of these are Python reimplementations with new names: `gulmc` (ground-up loss),
`fmpy` (financial module), `eltpy`, `lecpy`, `aalpy`. The pipeline is the same.

## Two layers

- **MDK** (`pip install oasislmf`): a Python command line that runs ktools directly on files.
  This is where models are built and debugged.
- **Platform** (OasisPlatform, deployed via OasisEvaluation): Docker containers that wrap the
  MDK in a REST API, job-queue workers, a database and a web UI. This is how production
  cat teams run it.

## What `scripts/step1_setup_oasis.sh` does

0. Checks disk and RAM. Adds 8 GB swap, because the 8 GB instance is tight for about 7 containers.
   The EBS volume should be 50 GB or more.
1. Installs Docker Engine and the compose plugin from Docker's official apt repository.
2. Clones OasisEvaluation and runs `install.sh`. That pulls the images, starts the stack and
   registers the PiWind demo model.
3. Checks the API: health check, token, list of registered models.
4. Runs PiWind end to end with the MDK. Outputs land in `runs/piwind_test/output/`.

The UI is reached through an SSH tunnel (`-L 8080:localhost:8080`), never through an open
security-group port. The default login is admin / password.

## Success criteria

- `docker ps` shows every container as up
- PiWind is in the models list
- The `output/` folder contains `*_eltcalc.csv`, `*_leccalc_*.csv` and `*_aalcalc.csv`
