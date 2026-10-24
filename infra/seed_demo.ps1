$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    & (Join-Path $PSScriptRoot 'start_localstack.ps1')
    & terraform '-chdir=infra/demo-terraform' init -input=false -no-color
    if ($LASTEXITCODE -ne 0) { throw 'Terraform initialization failed.' }
    # This fixture pins both AWS provider endpoints to localhost:4566.
    & terraform '-chdir=infra/demo-terraform' apply -auto-approve -input=false -no-color
    if ($LASTEXITCODE -ne 0) { throw 'LocalStack Terraform fixture failed.' }
    & uv run --directory backend python ../infra/seed_manual_demo.py
    if ($LASTEXITCODE -ne 0) { throw 'LocalStack manual fixture failed.' }
} finally {
    Pop-Location
}
