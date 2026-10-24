# CloudPilot

FastAPI, React + TypeScript, and SQLite foundation for the five-person team.
Person 5's LocalStack/MCP/LangChain approval workflow is implemented: prepare an
exact change, approve or reject it, then create a Terraform PR or change a manual
LocalStack instance and verify the result. Forecasting and optimization remain
separate team integrations; demo recommendations are explicitly labeled stubs.

See [Person 5 workflow](docs/PERSON_5_WORKFLOW.md) for setup, dashboard usage,
engine handoff, supported operations, recovery and live acceptance tests, and
[prerequisites](docs/PERSON_5_PREREQUISITES.md) for the local credentials.
The [acceptance record](docs/PERSON_5_ACCEPTANCE.md) separates unit checks from real
Bedrock, LocalStack and GitHub verification.

## Start locally

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and Node.js 22.12+ with npm.
Run from the repository root in two terminals:

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

Open [CloudPilot](http://localhost:5173) and [API docs](http://localhost:8001/docs).
The starter inventory works without credentials or Docker. Execution needs the
configured integrations and a local operator token. Configuration defaults work as-is; optional
overrides live in a root `.env` copied from `.env.example`. The frontend proxies
`/api` to the backend. SQLite files are created under `data/local/` and ignored by Git.
Execution registrations, approvals, proposals and audit events persist there.

## Starting points

Ownership follows [5people.md](5people.md). Keep the core delivery scope in
[PRODUCT_DEFINITION.md](docs/PRODUCT_DEFINITION.md).

| Person | Start here |
| --- | --- |
| 1 — data | `data/fixtures/`, `backend/app/adapters/`, source contracts in `backend/app/models/` |
| 2 — forecasting | `backend/app/ml/`, `experiments/` |
| 3 — API and optimizer | `backend/app/api/`, `engine/`, `repositories/`, `database.py` |
| 4 — frontend | `frontend/src/App.tsx`, `frontend/src/lib/api.ts` |
| 5 — integration and lab | `backend/app/agent/`, `mcp/`, `execution/`, `infra/` |

Use `backend/app/models/contracts.py` for shared Pydantic contracts; mirror consumed
fields in the frontend API types. Timestamps must include a timezone; metric names
declare absolute units. Money uses `Decimal` and is serialized as a JSON string.
Keep future domain logic in shared services so REST and MCP use the same rules.

The read-only starter endpoints are `GET /api/health`, `/api/resources`,
`/api/resources/{id}`, and `/api/plans`. Resource lists support environment, region,
team, limit and offset. Errors include code, message, details and request ID.
The fixture is synthetic and its INR compute rate is illustrative. It contains no
telemetry or recommendations; additional features should publish their contracts
as they are implemented. Add charts/Recharts when chart views are built.

## Check the foundation

```sh
uv run --directory backend pytest
npm --prefix frontend run build
```

Commit dependency lockfiles when changing dependencies. Generated data, virtual
environments, frontend builds and local configuration stay out of Git.
