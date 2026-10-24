$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
& docker compose --env-file (Join-Path $repoRoot '.env') -f (Join-Path $PSScriptRoot 'localstack/compose.yaml') up -d --wait --wait-timeout 180
if ($LASTEXITCODE -ne 0) { throw 'LocalStack startup failed.' }
