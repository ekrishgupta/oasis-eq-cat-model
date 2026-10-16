#!/usr/bin/env bash
# Run the whole LA earthquake model inside Docker on the EC2 host.
#   1. Build the pipeline image (Python stack) and run every data/model build step in it.
#   2. Start the LAEQ model worker in the Oasis platform (official coreoasis/model_worker).
#   3. Run the analysis through the Oasis platform API and download the outputs.
#   4. Compute deliverables, charts and sensitivity in the pipeline image.
# Usage: bash scripts/docker_pipeline.sh [build|worker|run|analyze|all]   (default: all)
set -euo pipefail
cd "$(dirname "$0")/.."
REPO=$(pwd)
IMAGE=laeq-pipeline:2.5.8
PLATFORM=${OASIS_EVALUATION_DIR:-$HOME/OasisEvaluation}
STEP=${1:-all}

in_docker() {  # run a command in the pipeline image with the repo mounted at /app
  docker run --rm --network host -u "$(id -u):$(id -g)" -e HOME=/tmp \
    -v "$REPO":/app -w /app "$IMAGE" "$@"
}

build() {
  docker build -t "$IMAGE" -f docker/Dockerfile.pipeline .
  in_docker python scripts/fetch_shakemaps.py
  in_docker python scripts/fetch_buildings.py
  if ls data/raw/hazus/*technical-manual-6-1*.pdf >/dev/null 2>&1; then
    in_docker python scripts/extract_hazus_csm_tables.py data/raw/hazus/*technical-manual-6-1*.pdf
  else
    echo "Hazus 6.1 manual not in data/raw/hazus/; using the committed data/hazus/csm tables"
  fi
  in_docker python scripts/extract_hazus_lf.py
  in_docker python scripts/build_vulnerability_csm.py
  in_docker python scripts/build_footprint.py
  in_docker python scripts/plot_footprints.py
  in_docker python scripts/build_exposure.py
  in_docker python scripts/build_rates.py
  in_docker bash scripts/compile_model_data.sh
}

worker() {
  LAEQ_REPO="$REPO" docker compose -p oasisevaluation -f "$PLATFORM/oasis-platform.yml" -f docker/laeq-worker.yml \
    up -d laeq-worker
}

run() {
  in_docker python scripts/run_platform.py
}

analyze() {
  in_docker python scripts/analyze_results.py
  in_docker python scripts/plot_results.py
  in_docker python scripts/sensitivity.py
  in_docker python scripts/plot_sensitivity.py
}

case "$STEP" in
  build) build ;;
  worker) worker ;;
  run) run ;;
  analyze) analyze ;;
  all) build; worker; run; analyze ;;
  *) echo "unknown step: $STEP"; exit 1 ;;
esac
