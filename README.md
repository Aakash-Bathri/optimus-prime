# CloudPilot

Cloud cost review with a small, explicit workflow: inspect resources, review evidence, queue a finding, and test an approved change in LocalStack or create a Terraform PR.

Read the short [TRD](docs/TRD.md) for architecture and [product audit](docs/PRODUCT_AUDIT.md) for corrections and remaining limits. The app opens directly into the local workspace; no demo account is needed.

## Run

With Docker Desktop running and a configured root `.env`:

```sh
docker compose up --build -d --wait
```

Open [CloudPilot](http://localhost:5173). The API is at [localhost:8001/docs](http://localhost:8001/docs). Compose seeds LocalStack and persists SQLite in its application volume. Do not overwrite an existing `.env` or remove volumes to refresh the UI.

For development with Python 3.12+, uv and Node.js 22.12+:

```sh
uv sync --directory backend
uv run --directory backend uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
npm --prefix frontend ci
npm --prefix frontend run dev
```

Run the API and frontend in separate terminals. Stop other services using the same ports first. `CLOUDPILOT_API_PROXY` can point the Vite proxy to another local API port. An explicit `VITE_API_BASE_URL` overrides that same-origin proxy, so clear it when testing with the proxy.

Analysis works without external credentials. The backend uses one shared HTTP client for LLM text; previews do not run a model tool loop. The first import validates and analyzes `test-data/`; later startups reuse the SQLite cache. Changing source data or analysis code rebuilds it atomically and invalidates old recommendation identities.

## Use

1. Open **Resources** and filter by environment, region or team. Inspect a resource's history.
2. Open **Recommendations**, inspect a candidate's peak/replay checks and queue it for review.
3. For a lab test, open **Execution lab**, connect the operator token if needed and register a manual or Terraform destination. Load candidate evidence and prepare a preview.
4. Approve the exact preview, then execute. Inspect the verified result and audit. A manual inverse change needs fresh approval. Terraform produces a PR for customer review, merge and apply.
5. Open **What-if & alerts**. Ask a plain-language question, review the LLM-filled inputs, then run it. Explain a finding from its drawer or the scenario page. Download a Markdown report or JSON evidence.

**What-if questions and explanations use the configured LLM.** Set `QWEN_API_KEY`, `QWEN_BASE_URL`, `QWEN_MODEL`, or the existing `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `CLOUDPILOT_LLM_MODEL`. Interpretation fails clearly when unavailable; scenario forms still work. Explanations label their evidence-summary fallback. Credentials stay server-side.

## Execution setup

Use `.env.example` as a reference. LocalStack needs its auth token and the MCP npm dependencies. For host execution, install Terraform and initialize the audited module. Seed the fixtures using:

```sh
npm --prefix infra/localstack-mcp ci
bash infra/seed_demo.sh --terraform
```

Windows has `infra/seed_demo.ps1`. Docker Compose supplies these runtime dependencies inside the API image.

Set `CLOUDPILOT_EXECUTION_TOKEN` to protect execution API calls. The operator connection form accepts it into page memory. Optional `CLOUDPILOT_LOCAL_TOKEN_PREFILL=true` is for a loopback-only demo; keep it off on public deployments.

For PRs, configure `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY_PATH` and `CLOUDPILOT_GITHUB_TEST_REPO`. Install the App on the dedicated demo repository with Contents and Pull requests write permission. Copy the audited files from `infra/demo-terraform/` to that repository, excluding state and `.terraform/`. Mount the PEM read-only when running in Docker. Keys and state must remain out of Git.

The integration accepts the audited root module and explicit instance-variable mapping. It validates Terraform format and syntax; it does not plan, merge or apply the PR. LocalStack execution tests AWS control-plane records, not actual workload performance.

## Data and limits

The synthetic benchmark has 200 resources: 150 VMs, 20 volumes, 20 public IPs and 10 GPUs. GPU/IP prices are unknown. Totals cover known charges only. Current compute comparisons use quarterly commitment price divided by three. Stopped VMs remain billable, so shutdown cash savings default to zero. An explicitly hypothetical hourly-billing scenario can compare prorated costs.

Historical billing is synthetic; daily values are allocated from monthly records. Utilization uses peaks and stress replay. Unknown provider capabilities block production eligibility. A queued finding or a LocalStack change cannot count as verified Utho savings. Energy/carbon estimates use editable assumptions.

Real tenant isolation, production Utho changes, automated deletion and unattended notifications are not implemented. The deployment guide at [infra/aws/README.md](infra/aws/README.md) describes the optional hosted demo, which disables execution server-side.

## Verify

```sh
uv run --directory backend pytest -q
npm --prefix frontend run build
```

The suite includes 15 dataset-to-execution API journeys with simulated external adapters. Live LLM, LocalStack MCP and Terraform PR results are recorded separately in [docs/verification](docs/verification). They are not interchangeable with unit-test coverage.

The longer historical walkthrough in `howtouse.md` describes earlier UI labels; this README and the TRD describe the current workflow.
