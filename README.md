# CloudPilot

**New to the project? Read [CloudPilot in plain English](howtouse.md).** It explains every dashboard page, Qwen, MCP, agents, GitHub PRs and a complete user flow.

A local cloud-cost review application built around the delivered `test-data/`
benchmark. FastAPI analyzes the source files, SQLite stores versioned results and
review decisions, and React presents inventory, telemetry, recommendation evidence,
a review plan, simulation and explained alerts. Analysis works without credentials.
The integrated execution lab adds approved LocalStack changes and GitHub PRs.

## Run with Docker Compose

Requires Docker Desktop running and a root `.env` file. Copy `.env.example` only
if `.env` does not exist. Set `LOCALSTACK_AUTH_TOKEN` and a random
`CLOUDPILOT_EXECUTION_TOKEN`. GitHub and LLM credentials are optional for the
manual scripted journey.

```sh
docker compose up --build -d --wait
```

Open http://localhost:5173. The API is at http://localhost:8001/docs. Compose
starts LocalStack, seeds the manual fixture, waits for API health, then serves
the dashboard through Nginx. MCP runs inside the API container over stdio.
No host Python, Node.js, Terraform or npm installation is needed.

Stop existing host servers on ports 5173/8001 first, or set
`CLOUDPILOT_WEB_PORT=5175 CLOUDPILOT_API_PORT=8003` before the Compose command. If the earlier standalone
LocalStack stack is running, stop it with
`docker compose --env-file .env -f infra/localstack/compose.yaml down` before starting this stack.

Follow `howtouse.md`, using **Register manual demo** and **Scripted tools**.
For optional GitHub execution, mount your PEM file read-only into the backend
with a Compose override and set `GITHUB_APP_PRIVATE_KEY_PATH` to its container
path. Keys are excluded from image builds. The Terraform provider is initialized
in the API image; the automatic seed creates only the manual fixture.

```sh
docker compose ps
docker compose logs -f backend seed localstack
docker compose down
```

SQLite and execution audit persist in `app-data`. LocalStack fixture persistence
depends on your license; rerun `docker compose run --rm seed` after a reset and
register it again. Avoid `down -v` unless intentionally deleting saved data.
The backend mounts the Docker socket because the official LocalStack MCP server
uses Docker exec. This grants Docker-engine access; use this stack locally with
trusted images. All published ports bind to localhost.

## Run locally

Requires Python 3.12+, uv, and Node.js 22.12+ with npm. From the repository root,
start two terminals:

```sh
# Terminal 1 — API
uv sync --directory backend
uv run --directory backend uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

```sh
# Terminal 2 — frontend
cd frontend
npm ci
npm run dev
```

Open [CloudPilot](http://localhost:5173) and [API documentation](http://localhost:8001/docs).
The API automatically imports and analyzes `test-data/` on its first startup
(about 12 seconds on the development machine). Later starts reuse the SQLite cache.
Changing a supported source file, analysis implementation or policy triggers an
atomic rebuild. Invalid source data stops startup with a diagnostic; partial
imports are never published. The frontend proxies `/api` to port 8001.

Configuration defaults work without a `.env` file. Optional overrides are in
[.env.example](.env.example). SQLite and generated builds are ignored by Git.
The supplied dataset is required; the old one-resource fixture has been replaced.

## What is implemented

- Validated inventory for **200 resources**: 150 VMs, 20 block volumes, 20 public
  IPs and 10 GPUs; 49 catalog configurations.
- Indexed import of **432,000 VM** and **28,800 GPU** observations, relationships,
  source events, resource prices and six months of synthetic billing.
- Thirty-day utilization charts with separate mean/peak series, CPU/RAM absolute
  demand, p50/p95/p99/max, EWMA/MAD and coverage/freshness evidence.
- Peak-aware, same-hardware/family enumeration; disk/transfer checks; historical
  and 1.2× stress replay; passed/failed/unknown provider gates for every candidate.
- Conditional resize/capacity findings, sustained-idle investigation, orphan review,
  explicit insufficient-data/no-action/unsupported outcomes.
- Overview, searchable inventory, combined region/environment/team/type filters,
  resource and evidence drawers, catalog-based demand simulation, and alerts.
- Transactional review decisions, stale-revision protection, audit history,
  reconciled current/accepted costs and JSON/CSV exports with evidence/assumptions.

**The supplied provider evidence is incomplete.** Region availability, resize,
IOPS/network and storage capabilities are unverified, so this benchmark produces
review findings rather than execution-ready changes. Queuing a finding saves a
review task; it does not reduce accepted-plan cost or authorize infrastructure
execution. Five VMs have insufficient telemetry. Ten identical event duplicates
are deduplicated and reported; conflicting duplicate IDs fail validation.

Money uses Decimal and is serialized as strings. Compute comparisons use
**quarterly commitment price / 3**, not a provider monthly tariff. Powered-off VMs
remain billable under the supplied assumptions, so stop/schedule cash savings are
zero. GPU/IP prices remain null: estate costs are explicitly incomplete. Source
prices are user-supplied and have not been independently verified. There are no
actual invoices or verified savings. Applied LocalStack changes are tracked separately.

## Try the application

The UI follows the relevant parts of the [OptScale open-source project](https://github.com/hystax/optscale): Home, Recommendations, Resources, FinOps → Cost Explorer, and System → Data sources.

1. Select **Use demo profile**, or enter a name and email. This is a browser-local
   profile, not authentication; it does not protect the API. The organization
   selector contains the one imported organization, **CloudPilot demo**.
2. Home shows latest organization expenses, top resource expenses, and optimization
   opportunities. Click a resource to inspect utilization and linked findings.
3. Recommendations includes category cards, the full findings table, evidence,
   capacity simulation, and the persistent **Review queue** with exports.
4. Resources supports combined source/environment/region/team/type/search filters,
   sorting, pagination, and detailed resource evidence.
5. Cost Explorer supports daily, weekly, monthly and custom date ranges, with
   breakdowns by data source, resource type, environment, region, and team.
   Click a chart segment or breakdown row to open the contributing resources and
   their expenses for that exact period. Browser back/forward preserves the
   resource drilldown URL.
6. System → Data sources classifies the imported Utho benchmark by resource type
   and source file. Click a classification to filter inventory.
7. Open the profile menu to sign out and return to the demo login screen.

Billing history covers April–September 2026. Daily and weekly values are even
allocations of synthetic monthly billing, with integer-paise rounding that
reconciles to the original totals. They are not measured daily charges. GPU and
public-IP prices remain unknown and are excluded from expense totals. The current
monthly cost equivalent and historical billing expenses are separate measures.

Useful read endpoints: `/api/dataset`, `/api/data-sources`, `/api/expenses`,
`/api/summary`, `/api/resources`, `/api/resources/{id}/metrics`, `/api/plans`,
`/api/recommendations`, `/api/recommendations/{id}`, `/api/optimization-plan`,
`/api/alerts`, `/api/audit`. `/api/expenses` accepts `start`, `end`, `granularity`
(`day`, `week`, `month`), `breakdown`, and the shared resource filters.
`PATCH /api/recommendations/{id}` requires `decision`, `version` and
`expected_revision`. `POST /api/simulate` accepts only resource/catalog IDs and a
bounded demand multiplier. OpenAPI describes request constraints.

## Validate

```sh
uv run --directory backend pytest -q
npm --prefix frontend run build
```

The tests exercise delivered-data import, independent peak/memory safety fixtures,
unknown capabilities, Decimal economics, missing observations, chart peaks,
combined-filter reconciliation, persisted decisions/restart, stale revisions,
exports, read-only simulation and atomic rollback on duplicate telemetry. Oracle
and workload-label files never enter the optimizer or source fingerprint.

## Plan and limits

[Implementation roadmap](docs/ENGINE_IMPLEMENTATION_ROADMAP.md) maps this increment
(M0–M4) and the remaining work to
[CloudPilot_Algorithms_and_Models.md](docs/CloudPilot_Algorithms_and_Models.md).
Read [assumptions](docs/assumptions.md), [architecture](docs/architecture.md) and
[acceptance results](docs/acceptance.md) for the precise behavior.

Remaining milestones: editable schedule/activity analysis (while respecting zero
stop savings), reviewed deletion prerequisites, a configured budget, optional
seasonal-naive/Ridge forecasting with evaluation, and the dedicated Docker
measurement lab. MCP, approved LocalStack operations and GitHub PRs are integrated.
Production Utho mutations remain blocked. This is not the full competition acceptance gate.
The earlier [product definition](docs/PRODUCT_DEFINITION.md) remains the broader
product intent; delivered dataset counts/pricing take precedence over its older
illustrative catalog assumptions.

If startup fails, inspect the named source validation error. If the UI cannot
connect, check that the API has finished importing on port 8001 and use Retry.
A changed dataset creates new recommendation IDs; prior decisions remain in the
audit history and must be reviewed against new evidence. Run `--reload` during
backend development so a stale API process does not serve old contracts.

## Execution lab setup

Read [howtouse.md](howtouse.md) for the short walkthrough. The full flow is:
dataset → engine finding → review queue → lab preview → exact approval →
manual LocalStack change or Terraform PR → verification.

Install **Docker Desktop with its engine running**, **Terraform 1.10+ below 2.0**,
Python 3.12+, uv and Node.js 22.12+. Keep ports 4566, 8001 and 5173 available.
LocalStack uses mock EC2 records, not real VM workloads.

Copy `.env.example` to `.env` if a local `.env` does not already exist. Set these
values locally; API keys, PEM files and Terraform state must stay out of Git:

| Setting | Required value |
| --- | --- |
| `LOCALSTACK_AUTH_TOKEN` | Your LocalStack token with access to the demo EC2 APIs |
| `OPENAI_BASE_URL` | `https://bedrock-mantle.us-east-1.api.aws/v1` |
| `OPENAI_API_KEY` | Bedrock Mantle API key; the client uses OpenAI-compatible naming |
| `CLOUDPILOT_LLM_MODEL` | `qwen.qwen3-coder-480b-a35b-instruct`, enabled in your AWS account |
| `CLOUDPILOT_EXECUTION_TOKEN` | A random local operator token to enter in the execution UI |
| `GITHUB_APP_ID` | GitHub App ID |
| `GITHUB_APP_PRIVATE_KEY_PATH` | Its PEM path, normally under ignored `github_app_private_key/` |
| `CLOUDPILOT_GITHUB_TEST_REPO` | Dedicated Terraform repository as `owner/repo` |
| `VITE_API_BASE_URL` | `http://127.0.0.1:8001` |

Create a GitHub App with **Contents: read/write** and **Pull requests: read/write**.
Install it on the dedicated demo repository. Copy the source files from
`infra/demo-terraform/` into that repo, including `cloudpilot.json` and the provider
lock file, but exclude state and `.terraform/`. The adapter supports this audited
root module and mapped instance-type variable. App ID, PEM and installation are
sufficient; OAuth Client ID/secret are only for a separate GitHub sign-in feature.

On macOS/Linux, run `bash infra/seed_demo.sh` for the manual journey, or add
`--terraform` to seed both destinations. On Windows:

```powershell
npm --prefix infra/localstack-mcp ci
.\infra\seed_demo.ps1
```

This starts LocalStack, waits for health, initializes Terraform and creates both
fixtures using localhost endpoints. If the LocalStack plan resets resources on
restart, rerun this command and register the fixtures again. **Scripted tools**
works without an LLM key. Real LLM calls use your Bedrock billing. GitHub credentials
are needed only for the Terraform route. Run one local API worker.

In **Execution lab**, enter the local token and connect/register the fixtures.
Queue an engine resize finding, open it in the lab, load evidence and choose a
candidate. Pick the manual destination for an EC2 change or Terraform for a PR.
Review and approve the exact preview, then execute separately. An inverse manual
change needs fresh approval. The customer reviews, merges and applies Terraform.

The bridge requires an exact supported CPU/RAM shape: m5.large (2/8 GiB),
m5.xlarge (4/16) or m5.2xlarge (8/32). Historical data, provider blockers and
hardware/storage limitations stay visible. A lab result does not authorize a
production change, prove workload performance or reduce the Utho cost plan.
Changed source decisions, evidence or live state invalidate the approval.

See [workflow and recovery details](docs/PERSON_5_WORKFLOW.md). Engine decisions,
approvals and execution audit persist in SQLite under ignored `data/local/`.

### Monitoring, forecasts and bonus features

Open **Monitoring & forecast** in the sidebar (`#/monitoring`). Existing environment,
region, team, resource type, search and data source filters scope every calculation,
alert, explanation and export.

- Forecast known INR costs over the next **30, 60 or 90 days**. Monthly billing is
  normalized to daily rates, then a linear trend is extrapolated. The chart shows a
  sensitivity range, with a minimum 10% band that widens with evidence age. This is
  not a calibrated confidence interval. The imported billing cutoff remains visible.
- Simulate stopping running development VMs **20:00–08:00** by default. Change the
  environment, local start/stop hours, IANA timezone, start weekdays, demand growth
  and full-horizon budget. Overnight windows belong to the day they start. Time
  windows are evaluated hourly. Storage remains charged. Savings assume prorated
  compute and can be zero under quarterly commitments.
- Review historical usage anomalies and data gaps, daily-normalized cost increases,
  CPU/memory p95 capacity risks and forecast budget overruns. Thresholds are editable.
  The page reevaluates every minute while open; this is an in-app alert feed, not an
  unattended notification worker or email integration.
- Compare allocated, estimated busy and avoided vCPU-hours. Sustainability estimates
  use allocated vCPU-hours × assumed watts/vCPU × PUE, then assumed kg CO2e/kWh.
  All three coefficients are editable. These are estimates, not metered energy or
  verified emissions reductions.
- Choose **Engineer**, **Finance**, or **Leadership** presentation views. Engineer
  includes capacity details and an IaC handoff; Finance emphasizes cost, budget and
  reports; Leadership presents consolidated cost and sustainability results. The
  existing team filter scopes the estate. These are local presentation preferences,
  **not authentication, authorization or secure multi-tenant isolation**.
- Ask Qwen to explain a scenario or a specific scoped recommendation. Credentials
  stay server-side. It uses `QWEN_API_KEY`, `QWEN_BASE_URL`, `QWEN_MODEL` when provided,
  otherwise the existing `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `CLOUDPILOT_LLM_MODEL`.
  The model name must contain `qwen`. Provider failures return an explicitly labeled
  deterministic explanation without leaking provider responses or credentials.
- Download a Markdown recommendation report or JSON evidence bundle. Engineer view
  also exports valid, provider-neutral Terraform `locals` containing schedule metadata
  and findings. This handoff creates no resources: verified provider resource mappings,
  scheduler wiring and review are required before applying any infrastructure change.

API: `POST /api/monitoring/evaluate`, `POST /api/monitoring/explain` and
`POST /api/monitoring/export?format=markdown|json|terraform`. Evaluation/export bodies
accept the scenario directly; explanation accepts `{ "scenario": {...},
"recommendation_id": "optional scoped finding ID" }`. Budgets apply to the entire
selected horizon. All costs exclude unavailable tariffs and use historical synthetic
fixtures. Changing inputs requires **Run scenario** before explanations or export.

### Deploy the investor demo to AWS

The [AWS Terraform deployment guide](infra/aws/README.md) provides a two-stage
Mumbai deployment: ECR/Secrets Manager bootstrap, then an authenticated HTTPS EC2
app with encrypted persistent storage, backups, logs and infrastructure alarms.
Hosted images disable the execution lab server-side and in the UI. A domain and
your AWS account configuration are required before applying; no cloud resources
are created by adding these files.

### Local dashboard execution demo

On Home, choose **Register manual demo** or **Register Terraform demo**. Registration
opens Execution lab, where you preview, approve and execute a change. The Terraform
workflow creates a PR in `CLOUDPILOT_GITHUB_TEST_REPO`; the customer merges and applies it.
The manual workflow changes only the tagged LocalStack fixture.

`docker compose up -d --build` now seeds both fixtures, persists the Terraform state
in `app-data`, and mounts `github_app_private_key/` read-only into the backend. Set
`GITHUB_APP_PRIVATE_KEY_PATH` to the matching relative PEM path and install the App
on the configured demo repository with Contents and Pull requests write access.

The loopback-bound Compose demo enables `CLOUDPILOT_LOCAL_TOKEN_PREFILL=true`, which
loads the operator token into page memory through an uncached local session endpoint.
This credential protects execution API writes and is separate from GitHub App auth.
The endpoint rejects non-local hosts and cross-site requests. It is opt-in outside
Compose and absent when execution is disabled. Keep it disabled on public deployments;
do not put the credential in a Vite bundle or browser storage.

Terraform preview validates the exact audited demo module with the backend’s verified
provider lock for its OS. The repository lock is preserved; the PR changes only the
mapped instance-size variable. This permits macOS-created demo repositories to be
validated inside Linux Docker without disabling provider checksum checks.
