# CloudPilot

A local cloud-cost review application built around the delivered `test-data/`
benchmark. FastAPI analyzes the source files, SQLite stores versioned results and
review decisions, and React presents inventory, telemetry, recommendation evidence,
a review plan, simulation and explained alerts. No credentials or paid service is
required.

## Run locally

Requires Python 3.12+, uv, and Node.js 22.12+ with npm. From the repository root,
start two terminals:

```sh
# Terminal 1 — API
uv sync --directory backend
uv run --directory backend uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```sh
# Terminal 2 — frontend
cd frontend
npm ci
npm run dev
```

Open [CloudPilot](http://localhost:5173) and [API documentation](http://localhost:8000/docs).
The API automatically imports and analyzes `test-data/` on its first startup
(about 12 seconds on the development machine). Later starts reuse the SQLite cache.
Changing a supported source file, analysis implementation or policy triggers an
atomic rebuild. Invalid source data stops startup with a diagnostic; partial
imports are never published. The frontend proxies `/api` to port 8000.

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
actual invoices, applied changes or verified savings.

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
measurement/approval/restore lab. Provider mutations, GitOps and MCP integration
are not implemented. This increment is not the full competition acceptance gate.
The earlier [product definition](docs/PRODUCT_DEFINITION.md) remains the broader
product intent; delivered dataset counts/pricing take precedence over its older
illustrative catalog assumptions.

If startup fails, inspect the named source validation error. If the UI cannot
connect, check that the API has finished importing on port 8000 and use Retry.
A changed dataset creates new recommendation IDs; prior decisions remain in the
audit history and must be reviewed against new evidence. Run `--reload` during
backend development so a stale API process does not serve old contracts.
