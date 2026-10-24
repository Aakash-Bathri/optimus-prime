# Verification record — 24 October 2026

- Full backend suite after architecture simplification and dependency removal: **153 passed**. This includes **15 automated dataset-to-execution API journeys** using the real dataset, recommendation engine, SQLite, approval boundary and simulated external adapters.
- The 153-test run includes the scenario validation, DST, daily-rate alerts, generic-model support and finding-fallback regressions. A focused monitoring run also passed 31 tests.
- Frontend: TypeScript and Vite production build passed.
- **15 additional live API journeys** exercised the real LocalStack MCP transport. Each imported/queried inventory and telemetry, queued the `vm-115` finding, chose an eligible lab shape, prepared a proposal, rejected execution before approval, approved and executed, verified instance type and preserved state, repeated execution, and downloaded the plan export. See `live-journeys.json` for each proposal ID.
- The refreshed live run uses one LLM-generated preview followed by fourteen evidence-summary previews; the model has no tools. Each record includes its dataset version. The live runner alternated `m5.xlarge` and `m5.2xlarge` on the tagged `demo-manual-01` fixture. Restoration is separately recorded in `live-restoration.json`. It restored the starting `m5.2xlarge` shape through a separately approved inverse proposal and restored the source decision. These were API-driven journeys, not 15 manual browser sessions. The UI received separate browser checks.
- Real GitHub/Terraform validation created [demo PR #3](https://github.com/Harshavardhan2903/cloudpilot-terraform-demo/pull/3). Format and validation passed; repeat execution returned the same PR. No merge, Terraform plan or apply was performed. See `live-pr.json`.
- Real Qwen interpretation and explanation results are recorded in `live-llm.json`. The check asserts Monday–Friday equals `[0,1,2,3,4]`, staging, 20:00–08:00, a 60-day horizon, commitment billing and zero stop cash savings. The final explanation check rejects a dollar symbol; explanations may omit currency when they do not quote monetary amounts.
- Browser checks covered direct workspace entry, scenario controls, corrected zero cash savings, finding evidence, stale-dataset refresh recovery and the plain-language explanation control. `scenario-ui.png` records the simplified entry view.

An earlier development run stopped after eight passes when auto-reload rebuilt the dataset; stale evidence was correctly refused. The final fifteen-pass run used a stable server. PR verification initially exposed an uninitialized local Terraform provider; initialization resolved it. Neither initial failure is counted as a successful journey.

These checks verify the prototype's implemented workflow. They do not establish real VM performance, Utho production compatibility, tenant authentication or actual invoice savings.

Reproduce the live manual passes with `backend/.venv/bin/python infra/verify_live_journeys.py` after starting the API on port 8002. It uses execution credentials from the local `.env` and changes only the tagged LocalStack demo fixture.

## Import and recovery audit

The additional dataset checks cover duplicate columns/keys, malformed manifests, time-grid/count reconciliation, attachment consistency, invalid observations, GPU memory limits, source event provenance/timing and billing gaps/duplicates. A mid-import source mutation check verifies that the previous snapshot remains published. GitHub encoding/authentication errors and ambiguous branch writes have dedicated tests. Read-only inspection of the existing demo PR is recorded in `live-pr-recovery.json`; no new PR was created for this audit. CSV export tests also cover formula-like text and preservation of negative numeric costs.

Final focused checks after MCP timeout/recovery corrections: **52 passed**; frontend production build and whitespace checks passed. These checks cover bounded provider deadlines, sanitized failures and recovery after a missing fixture.
