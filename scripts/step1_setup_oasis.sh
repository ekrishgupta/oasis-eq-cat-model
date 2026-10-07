#!/usr/bin/env bash
# Step 1: install Docker, bring up the Oasis platform, and run PiWind end to end.
# Target: Ubuntu 22.04/24.04 on EC2 (m7i-flex.large: 2 vCPU, 8 GB RAM).
# Run as the default user (ubuntu):  bash step1_setup_oasis.sh
set -euo pipefail

echo "== 0. Machine check =="
nproc; free -h; df -h /
ROOT_FREE_GB=$(df --output=avail -BG / | tail -1 | tr -dc '0-9')
if [ "$ROOT_FREE_GB" -lt 25 ]; then
  echo "WARNING: only ${ROOT_FREE_GB}GB free on /. Oasis images are ~10GB and the LA exposure"
  echo "         + ShakeMaps need more. Grow the EBS volume to 50GB+ before continuing."
fi

# 8 GB RAM is tight for the full stack (MySQL/Postgres, RabbitMQ, Redis, API, workers, UI).
# A swap file stops the kernel OOM-killing a container during a run.
if ! swapon --show | grep -q swapfile; then
  echo "== Adding 8GB swap =="
  sudo fallocate -l 8G /swapfile && sudo chmod 600 /swapfile
  sudo mkswap /swapfile && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

echo "== 1. Docker Engine + compose plugin (official apt repo) =="
if ! command -v docker >/dev/null; then
  sudo apt-get update -y
  sudo apt-get install -y ca-certificates curl git python3-venv python3-pip jq
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo usermod -aG docker "$USER"
fi
sudo docker run --rm hello-world | head -3
# Some older Oasis scripts call `docker-compose` (v1 syntax); shim it to the v2 plugin.
if ! command -v docker-compose >/dev/null; then
  printf '#!/bin/sh\nexec docker compose "$@"\n' | sudo tee /usr/local/bin/docker-compose >/dev/null
  sudo chmod +x /usr/local/bin/docker-compose
fi

echo "== 2. Oasis platform via OasisEvaluation =="
cd ~
[ -d OasisEvaluation ] || git clone https://github.com/OasisLMF/OasisEvaluation.git
cd OasisEvaluation
# install.sh pulls the API server, worker and UI images, clones PiWind as the demo model,
# starts everything with docker compose, and registers PiWind with the API.
# `sg docker` runs it with the new docker group without needing to log out/in.
sg docker -c "./install.sh"

echo "== 3. Verify the stack =="
sg docker -c "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
for i in $(seq 1 30); do
  curl -sf http://localhost:8000/healthcheck/ >/dev/null && break; sleep 10
done
TOKEN=$(curl -s -X POST http://localhost:8000/access_token/ \
  -H 'Content-Type: application/json' -d '{"username":"admin","password":"password"}' | jq -r .access_token)
echo "Registered models:"
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/v1/models/ | jq '.[] | {id, supplier_id, model_id, version_id}' \
  || curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/v2/models/ | jq .

echo "== 4. PiWind end to end with the MDK (same engine, no API in between) =="
cd ~
python3 -m venv ~/oasis-venv
source ~/oasis-venv/bin/activate
pip install -q --upgrade pip
pip install -q oasislmf          # Model Development Kit: Python + ktools/pytools binaries
oasislmf --version
[ -d OasisPiWind ] || git clone https://github.com/OasisLMF/OasisPiWind.git
cd OasisPiWind
# oasislmf.json points at PiWind's keys data, model_data (footprint/vulnerability) and a 10-location test portfolio.
oasislmf model run --config oasislmf.json -r runs/piwind_test
echo "Outputs:"; ls runs/piwind_test/output/
head -5 runs/piwind_test/output/*gul_S1_aalcalc*.csv 2>/dev/null || true
head -5 runs/piwind_test/output/*gul_S1_leccalc_full_uncertainty_oep*.csv 2>/dev/null || true

echo
echo "Done. From your laptop, open the UI through an SSH tunnel (don't open 8080/8000 in the security group):"
echo "  ssh -i <key>.pem -L 8080:localhost:8080 -L 8000:localhost:8000 ubuntu@<ec2-public-dns>"
echo "  then browse http://localhost:8080  (admin / password)"
