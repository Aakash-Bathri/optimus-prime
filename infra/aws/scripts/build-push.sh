#!/usr/bin/env bash
# Build the two hosted images for x86 EC2 and push immutable tags to bootstrap ECR.
set -euo pipefail
TASK_ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
for tool in aws docker terraform python3; do command -v "$tool" >/dev/null || { echo "Missing $tool" >&2; exit 1; }; done
if env | grep -q '^AWS_ENDPOINT_URL'; then echo 'Remove AWS endpoint overrides before deploying to real AWS.' >&2; exit 1; fi
TAG=${1:-$(git -C "$TASK_ROOT" rev-parse --short=12 HEAD)-$(date -u +%Y%m%dT%H%M%SZ)}
[[ "$TAG" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ && "$TAG" != latest ]] || { echo 'Use a versioned image tag.' >&2; exit 1; }
OUTPUTS=$(terraform -chdir="$TASK_ROOT/infra/aws/bootstrap" output -json)
REGION=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["aws_region"]["value"])' <<< "$OUTPUTS")
BACKEND=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["backend_repository_url"]["value"])' <<< "$OUTPUTS")
FRONTEND=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["frontend_repository_url"]["value"])' <<< "$OUTPUTS")
REGISTRY=${BACKEND%%/*}
# Validate caller identity without printing credentials.
aws sts get-caller-identity --region "$REGION" --query '{Account:Account,Arn:Arn}'
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY"
trap 'docker logout "$REGISTRY" >/dev/null 2>&1 || true' EXIT
for SERVICE in backend frontend; do
    if [ "$SERVICE" = backend ]; then REPO=$BACKEND; else REPO=$FRONTEND; fi
    docker buildx build --platform linux/amd64 --provenance=false --push \
      -f "$TASK_ROOT/infra/aws/$SERVICE.Dockerfile" -t "$REPO:$TAG" "$TASK_ROOT"
done
python3 - "$BACKEND:$TAG" "$FRONTEND:$TAG" <<'PY'
import json, sys
print('\nSet these values in demo/terraform.tfvars:')
print('backend_image  = ' + json.dumps(sys.argv[1]))
print('frontend_image = ' + json.dumps(sys.argv[2]))
PY
