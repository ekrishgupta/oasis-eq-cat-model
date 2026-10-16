"""Run the LA earthquake model through the Oasis platform (Docker) API.

Steps, all against the platform at OASIS_API_URL (default http://localhost:8000):
  1. find the registered model KrishGupta / LAEQ / 1 (served by the laeq-worker container)
  2. create a portfolio and upload the OED location file
  3. create an analysis with model/analysis_settings.json
  4. generate Oasis input files (keys lookup etc.) on the platform workers
  5. run the losses on the platform workers
  6. download the output tarball and extract the ORD CSVs to outputs/oasis_run/

Inputs:  inputs/oed_location_la.csv, model/analysis_settings.json
Outputs: outputs/oasis_run/*.csv, outputs/oasis_run/platform_run.json
"""
import json
import logging
import os
import shutil
import tarfile
import time
from pathlib import Path

from oasislmf.platform_api.client import APIClient

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/oasis_run"
MODEL = {"supplier_id": "KrishGupta", "model_id": "LAEQ", "version_id": "1"}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    client = APIClient(api_url=os.environ.get("OASIS_API_URL", "http://localhost:8000"),
                       auth_type="simple", username="admin", password="password", timeout=900)

    models = [m for m in client.models.get().json()
              if all(m.get(k) == v for k, v in MODEL.items())]
    if not models:
        raise SystemExit(f"model {MODEL} is not registered; start docker/laeq-worker.yml first")
    model_id = models[0]["id"]
    logging.info(f"model {MODEL} has platform id {model_id}")

    stamp = time.strftime("%Y%m%d-%H%M%S")
    portfolio = client.upload_inputs(portfolio_name=f"LA County {stamp}",
                                     location_fp=str(ROOT / "inputs/oed_location_la.csv"))
    analysis = client.create_analysis(portfolio["id"], model_id, analysis_name=f"LAEQ {stamp}",
                                      analysis_settings_fp=str(ROOT / "model/analysis_settings.json"))
    analysis_id = analysis["id"]
    t0 = time.time()
    client.run_generate(analysis_id, poll_interval=10)
    t1 = time.time()
    client.run_analysis(analysis_id, poll_interval=10)
    t2 = time.time()

    tmp = ROOT / "outputs/.platform_download"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    client.download_output(analysis_id, download_path=str(tmp))
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    with tarfile.open(next(tmp.glob("*.tar.gz"))) as tar:
        for member in tar.getmembers():
            if member.isfile() and member.name.endswith(".csv"):
                member.name = Path(member.name).name
                tar.extract(member, OUT, filter="data")
    shutil.rmtree(tmp)

    (OUT / "platform_run.json").write_text(json.dumps({
        "api_url": client.api.url_base, "model": MODEL, "model_platform_id": model_id,
        "portfolio_id": portfolio["id"], "analysis_id": analysis_id,
        "input_generation_seconds": round(t1 - t0), "loss_run_seconds": round(t2 - t1),
        "completed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }, indent=2))
    logging.info(f"outputs: {sorted(p.name for p in OUT.glob('*.csv'))}")


if __name__ == "__main__":
    main()
