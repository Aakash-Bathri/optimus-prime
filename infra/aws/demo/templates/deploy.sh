#!/usr/bin/env bash
set -euo pipefail
umask 077
cd /opt/cloudpilot
mountpoint -q /srv/cloudpilot
python3 /opt/cloudpilot/load-secrets.py
REGION=$(python3 -c 'import json; print(json.load(open("config.json"))["region"])')
REGISTRY=$(python3 -c 'import json; print(json.load(open("config.json"))["registry"])')
export DOCKER_CONFIG=/run/cloudpilot/docker-auth
mkdir -p "$DOCKER_CONFIG"
trap 'docker logout "$REGISTRY" >/dev/null 2>&1 || true; rm -rf "$DOCKER_CONFIG"' EXIT
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY" >/dev/null
docker compose -f compose.yaml pull
# Validate the gateway before replacing any running containers.
docker compose -f compose.yaml run --rm --no-deps gateway caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
# Rotation must recreate containers; env file changes alone are not detected by all releases.
docker compose -f compose.yaml up -d --force-recreate --remove-orphans --wait --wait-timeout 900
# Confirm execution endpoints are actually absent from the hosted API.
docker compose -f compose.yaml exec -T backend python -c 'import json,urllib.request; paths=json.load(urllib.request.urlopen("http://localhost:8001/openapi.json"))["paths"]; assert not any(p.startswith("/api/execution") for p in paths)'
