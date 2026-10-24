#!/usr/bin/env bash
# Run from any directory. Default setup needs no Terraform/GitHub credentials.
set -euo pipefail
cd "$(dirname "$0")/.."
npm --prefix infra/localstack-mcp ci
docker compose --env-file .env -f infra/localstack/compose.yaml up -d --wait --wait-timeout 180
uv run --directory backend python ../infra/seed_manual_demo.py
if [[ "${1:-}" == "--terraform" ]]; then
  terraform -chdir=infra/demo-terraform init -input=false -no-color
  terraform -chdir=infra/demo-terraform apply -auto-approve -input=false -no-color
fi
