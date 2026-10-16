#!/usr/bin/env bash
# Run the LA earthquake model end to end with the Oasis MDK:
# keys lookup -> Oasis input files -> gulmc ground-up loss -> ELT, AAL and EP curves.
set -euo pipefail
cd "$(dirname "$0")/.."
RUN_DIR=${1:-runs/la_eq}

bash scripts/compile_model_data.sh
rm -rf "$RUN_DIR"
time oasislmf model run --config oasislmf.json -r "$RUN_DIR"
ls -lh "$RUN_DIR/output"
