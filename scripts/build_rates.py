"""Attach annual rates to the eight events and simulate a year-by-year occurrence catalogue.

Rates come from UCERF3 (USGS Fact Sheet 2015-3009), Los Angeles region: the average repeat
time of an earthquake of at least magnitude M. The annual exceedance rate is
N(>=M) = 1 / repeat time; between the published magnitudes we interpolate log10 N linearly
in M (a piecewise Gutenberg-Richter relation).

Each event stands for every LA-region earthquake in its magnitude band, so its annual rate
is N(>= lower edge) - N(>= upper edge). Band edges sit halfway between neighbouring events.
This treats every quake in a band as if it hit where the historical one did - conservative,
because many real ruptures in the region are farther from the dense urban core.

We then simulate N_YEARS independent years: in each year, event e occurs Poisson(rate_e)
times. That is the Oasis occurrence file; Oasis computes the EP curve from it.

Outputs: model_data/events_p.csv, model_data/occurrence_lt.csv, outputs/rates/event_rates.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/rates"

# UCERF3 LA region: magnitude threshold -> average repeat time (years).
UCERF3_LA_REPEAT_YEARS = {5.0: 1.4, 6.0: 10, 6.7: 40, 7.0: 61, 7.5: 109, 8.0: 532}
LOWEST_EDGE = 5.75   # below this, shaking is too weak to matter for building loss
N_YEARS = 100_000
SEED = 7


def exceedance_rate(m: float) -> float:
    mags = np.array(list(UCERF3_LA_REPEAT_YEARS))
    log_rates = np.log10(1 / np.array(list(UCERF3_LA_REPEAT_YEARS.values())))
    # Extrapolate past M8 with the slope of the last segment.
    if m > mags[-1]:
        slope = (log_rates[-1] - log_rates[-2]) / (mags[-1] - mags[-2])
        return 10 ** (log_rates[-1] + slope * (m - mags[-1]))
    return 10 ** np.interp(m, mags, log_rates)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    events = pd.read_csv(ROOT / "data/events.csv").sort_values("magnitude").reset_index(drop=True)
    mags = events["magnitude"].to_numpy()
    lower = np.concatenate([[LOWEST_EDGE], (mags[:-1] + mags[1:]) / 2])
    upper = np.concatenate([(mags[:-1] + mags[1:]) / 2, [np.inf]])
    events["band_lower"], events["band_upper"] = lower, upper
    events["annual_rate"] = [exceedance_rate(lo) - (0 if np.isinf(hi) else exceedance_rate(hi))
                             for lo, hi in zip(lower, upper)]
    events["return_period_years"] = 1 / events["annual_rate"]
    events.round(6).to_csv(OUT / "event_rates.csv", index=False)
    print(events[["event_id", "name", "magnitude", "band_lower", "band_upper",
                  "annual_rate", "return_period_years"]].round(4).to_string(index=False))

    rng = np.random.default_rng(SEED)
    rows = []
    for ev in events.itertuples():
        counts = rng.poisson(ev.annual_rate, N_YEARS)
        years = np.repeat(np.arange(1, N_YEARS + 1), counts)
        rows.append(pd.DataFrame({"event_id": ev.event_id, "period_no": years}))
    occ = pd.concat(rows).sort_values(["period_no", "event_id"]).reset_index(drop=True)
    occ["occ_year"] = occ["period_no"]
    occ["occ_month"] = rng.integers(1, 13, len(occ))
    occ["occ_day"] = rng.integers(1, 29, len(occ))

    pd.DataFrame({"event_id": sorted(events["event_id"])}).to_csv(ROOT / "model_data/events_p.csv", index=False)
    occ.to_csv(ROOT / "model_data/occurrence_lt.csv", index=False)
    print(f"\n{N_YEARS:,} simulated years, {len(occ):,} event occurrences "
          f"({len(occ) / N_YEARS:.3f}/yr vs expected {events['annual_rate'].sum():.3f}/yr)")


if __name__ == "__main__":
    main()
