#!/usr/bin/env bash
# Convert the model's CSV files to the binary formats the Oasis calculation engine reads.
# csvtobin ships with oasislmf 2.5 (Python replacement for the old ktools *tobin tools).
set -euo pipefail
cd "$(dirname "$0")/../model_data"

N_INTENSITY_BINS=$(($(wc -l < intensity_bin_dict.csv) - 1))
N_DAMAGE_BINS=$(($(wc -l < damage_bin_dict.csv) - 1))
N_PERIODS=$(python -c "import json; print(json.load(open('../model/model_settings.json'))['model_settings']['event_occurrence_id']['options'][0]['max_periods'])")

csvtobin damagebin     -i damage_bin_dict.csv -o damage_bin_dict.bin
csvtobin vulnerability -i vulnerability.csv   -o vulnerability.bin -d "$N_DAMAGE_BINS"
csvtobin footprint     -i footprint.csv       -o footprint.bin -x footprint.idx -m "$N_INTENSITY_BINS"
csvtobin eve           -i events_p.csv        -o events_p.bin
csvtobin occurrence    -i occurrence_lt.csv   -o occurrence_lt.bin -P "$N_PERIODS"
csvtobin returnperiods -i returnperiods.csv   -o returnperiods.bin
ls -lh *.bin *.idx
