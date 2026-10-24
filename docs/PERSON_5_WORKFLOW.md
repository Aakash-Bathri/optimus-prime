# Person 5 change workflow

The agreed five-step integration is implemented in `backend/app/agent/`,
`backend/app/mcp/`, and `backend/app/execution/`. It uses the existing FastAPI app,
SQLite and React dashboard. Person 2/3's recommendation engine can supply the
`Recommendation` contract; until then the dashboard uses explicitly labeled stubs.

## Run

From the project root:

```powershell
uv sync --directory backend
npm --prefix frontend ci
npm --prefix infra/localstack-mcp ci
.\infra\seed_demo.ps1
# Run in separate terminals:
uv run --directory backend uvicorn app.main:app --host 127.0.0.1 --port 8001
npm --prefix frontend run dev
```

Open http://localhost:5173. Enter `CLOUDPILOT_EXECUTION_TOKEN` from your ignored root
`.env` in the **Local operator token** field. This token protects the local demo API;
it is separate from GitHub App and Bedrock credentials and is never sent to either.
The browser keeps it in memory, not local storage. On a fresh checkout generate it
locally, for example with Python's `secrets.token_urlsafe(32)`, and save it in `.env`.

Click **Register demo resources**, choose a resource, then **Prepare change preview**.
Review the before/after configuration, evidence source, expiry, steps and diff.
**Approve this exact change** records approval. A separate execution button either
creates the PR or changes LocalStack. **Reject** prevents execution. The proposal
list and audit history survive refresh/restart.

For a manual change, **Prepare inverse change for review** creates a new preview;
it needs its own approval before restoring the original type or reversing stop/start.
For Terraform, the customer reviews, merges and applies the PR. Undo after apply
requires a reviewed revert PR. No cloud apply is performed by this application.

## Integrations and boundaries

- Bedrock Mantle uses the endpoint/model configured from `gate_pass`. A LangChain
  agent must inspect the resource, read the Terraform source when applicable, and
  call `prepare_change`. Tools cannot approve or execute. Scripted mode uses the
  same preparation tools without making an LLM request; LLM failures do not silently
  switch to scripted mode.
- All live AWS calls use the official LocalStack MCP server through the LangChain
  adapter. The executable fixes the container/endpoint and region. It exposes typed
  EC2 inspection, resize and stop/start operations rather than accepting raw user
  AWS commands. Only owned fixtures tagged `CloudPilotDemo=true` are eligible.
- Every registration explicitly records `terraform` or `manual`. Terraform adds
  repository, address, file and variable. The configured repository must be
  installed on the GitHub App and its `cloudpilot.json` mapping must match.
- The initial Terraform adapter supports the audited single-root EC2 demo template
  and an instance-type variable in `.tfvars.json`. Different modules/providers,
  arbitrary HCL edits, deletion, scheduling, volumes, IPs and real Utho/AWS changes
  require additional adapters. They are not silently treated as supported operations.
- Terraform source is pinned to a GitHub commit. A deterministic patch changes only
  the mapped variable, and Terraform fmt/validate use the locally initialized pinned
  AWS provider. No remote module/provider code is installed during preview. The
  candidate is **not plan-validated or benchmark-verified**.
- GitHub uses short-lived, repository-scoped installation tokens. App ID + PEM are
  sufficient for this bot workflow. OAuth Client ID/secret are needed only for a
  separate user sign-in feature. The private key and tokens are never given to the LLM.

## Engine handoff

`POST /api/execution/proposals` accepts `{recommendation, mode}`. Exact schemas live
in `backend/app/execution/contracts.py` and in `/docs`. Supply an ID, registered
resource ID, `resize`/`stop`/`start`, target instance type for resize, and evidence:
version, timezone-aware observed/expiry timestamps, checks_passed, source and reason.
Use `source=engine` for actual engine results. A failed check, expired/future evidence,
or evidence older than the default one hour blocks preparation and execution.
Stub checks demonstrate only the control plane and establish no workload safety.

The same service backs all decisions and executions. Approval binds the full
recommendation/evidence, explicit binding, current snapshot, pinned commit, patch
and operation steps to a digest. Changed live state, ownership, registration or
GitHub base invalidates it. Duplicate execution of a completed proposal returns
the existing result. Resource leases prevent concurrent changes.

## Recovery and audit

Use one local API worker. A partial/uncertain mutation or an API interruption
leaves `RECOVERY_REQUIRED` and holds the resource lease. The dashboard's **Read live
state and acknowledge failure** records fresh state and releases the lease; it
does not retry or claim success. Inspect the audit, then prepare a fresh approved
change as needed. A failed resize can leave an instance stopped; no automatic
rollback is claimed. A failed PR request can leave a branch/commit; audit includes
its branch name so the operator can inspect GitHub.

LocalStack's current license resets EC2 records on restart. Run
`./infra/seed_demo.ps1`, then register the fixtures again. The old proposals remain
in the audit and cannot execute against replaced provider IDs.

## Checks

```powershell
uv run --directory backend pytest -q
npm --prefix frontend run build
# Explicit live test: billed LLM calls, approved demo resize + restore, real test PR.
uv run --directory backend python ../infra/test_person5_live.py --mode llm --create-pr
```

Unit tests use fake integrations and cover lifecycle/security behavior. The live
harness uses real Bedrock, MCP, LocalStack and GitHub, verifies rejection,
idempotency and restore, and saves its result to ignored `data/local/person5-live.json`.
It never merges or applies the Terraform PR. Running it again creates another test
PR. The README/prerequisite guide documents credential setup without storing values.
