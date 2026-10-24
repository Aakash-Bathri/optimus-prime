# Integration verification — 24 October 2026

The engine and execution service share the FastAPI application and SQLite store.
The execution bridge preserves source recommendation/version/revision references,
requires capacity eligibility and an exact supported lab shape, and revalidates
source decisions before approval and execution.

## Verified

- Backend suite: 47 tests passed, including engine-to-execution routes, stale
  approvals, concurrent execution claims, expiry, partial failure recovery,
  restart recovery, inverse changes and manual registration without GitHub.
- Frontend: TypeScript and production Vite build passed.
- Actual pinned LocalStack container started healthy; official MCP server returned
  the seeded manual fixture.
- Live API: queued `vm-115`, selected `amd-basic-5`, prepared and approved the exact
  preview, and executed through MCP. LocalStack read-back confirmed `m5.xlarge`
  and `running` with `APPLIED` status.
- A separately prepared and approved inverse proposal restored `m5.2xlarge`
  and `running` through MCP.
- Browser: demo login, inventory (200 resources), recommendations, evidence drawer,
  handoff to execution, token connection, candidate loading, preview, approval,
  apply and verified `APPLIED` result (`m5.xlarge`, `running`). Home, Cost
  Explorer and Data sources also loaded successfully.
- Browser proof: `integration-applied.png`. The final demo fixture remains
  resized to `m5.xlarge`, running; the inverse route was verified separately.

## Scope

LocalStack uses mock EC2 records; these checks establish control-plane behavior.
Historical Utho data, provider blockers and cost-plan totals retain their original
meaning. Production changes and measured workload savings are not established.
Terraform/GitHub execution is covered by isolated integration tests; a real PR
and customer Terraform apply are separate from the verified manual MCP route.

## Repeat

Start Docker, set the LocalStack and local operator tokens in `.env`, then run
`bash infra/seed_demo.sh` on macOS/Linux. Start the API and frontend as described
in README. Follow `howtouse.md`; keep Scripted tools selected for the first run.

## Docker Compose verification

Both images built successfully. `docker compose up -d --wait` completed with
LocalStack and API healthy, seed exited 0, and Nginx running. Verified dashboard
HTML and `/api/dataset` through Nginx. Verified official stdio MCP inventory from
inside the API container. A real engine-linked resize then completed with
`APPLIED`, `m5.xlarge`, `running` (proposal
`b2b436a2-9e0a-45fb-8016-ddba07e5b5ec`). Testing used host ports 5175/8003 to
avoid interrupting existing host development servers. Default ports remain
5173/8001. All 47 backend tests passed after environment configuration changes.
