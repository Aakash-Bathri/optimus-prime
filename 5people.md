# CloudPilot — Five-Person Implementation Plan

Based on [CLOUDPILOT_MASTER_SPEC.md](CLOUDPILOT_MASTER_SPEC.md). This plan replaces its four-person allocation with **five implementation owners**, within the same **40–42-hour window**. Each numbered section belongs to one person; the steps inside it are in implementation order.

**Product flow:** Collect data → forecast demand → select a valid plan and calculate savings → validate the proposal → explain and display evidence → obtain approval → prepare a change → monitor the outcome.

**Working rule:** Get one complete local workflow running before adding optional integrations. The application must run without cloud credentials. Synthetic data, modeled outcomes, measured benchmarks, dry runs, and live changes must have distinct labels.

## 1. Person 1 — Data Foundation, Provider Catalogue, and Ingestion

**Goal:** Give every other person consistent, reproducible resource, telemetry, dependency, and pricing data.

**Own:** `data/`, `backend/app/adapters/`, data ingestion, Parquet/DuckDB datasets, and the resource/metric/catalogue schemas in `backend/app/models/`.

**Implementation steps**

1. **Lead the shared contract meeting during hours 0–2.** All five people agree on IDs, units, UTC timestamps, currency, API response shapes, and version fields. Person 3 owns the FastAPI application and recommendation/change schemas; you own the source-data schemas. Commit small JSON examples immediately so the frontend and agent can start with fixtures.
2. **Define the core data records.** Create resource, metric, provider-plan, price, dependency, and billing-snapshot records. Include region, environment, owner, team, criticality, management type, and provenance. Keep CPU demand in cores and memory demand in GiB available alongside utilization percentages, so resizing comparisons use absolute demand.
3. **Generate the synthetic estate.** Use a fixed seed to create 120 VMs, 30 days of 15-minute telemetry, and exactly 345,600 VM observations. Add volumes, IPs, dependencies, and six-month billing snapshots separately. Include steady-low, bursty, batch, weekday-only, memory-bound, network-bound, and insufficient-data workloads.
4. **Create the demo fixtures deliberately.** Include an eight-vCPU production API with two- and four-vCPU candidates, a development scheduling opportunity, an orphaned volume with unknown ownership, missing telemetry, and a cost/utilization anomaly. Coordinate expected behavior with Persons 2 and 3; derive results from inputs instead of hardcoding success.
5. **Build a versioned plan and pricing catalogue.** Store region availability, capacity, compatibility, compute/storage/IP charges, billing rules, currency, source, and effective date. Label fixture prices as illustrative. Before claiming real Utho savings, verify current prices, plan IDs, and billing behavior from provider sources.
6. **Implement ingestion behind a common adapter interface.** Deliver the synthetic adapter first. Add a bounded public-trace import for Person 2, preserving attribution and metric semantics. For example, throughput must not be silently treated as disk capacity or IOPS. Add read-only Utho ingestion only if credentials and time permit.
7. **Validate and package the data.** Check record counts, duplicate timestamps, units, missingness, resource references, plan references, and catalogue versions. Supply one repeatable generation/import command and a compact data dictionary.

**Handoffs**

| By | Deliverable | Recipient |
| --- | --- | --- |
| Hour 2 | Agreed schemas and sample JSON responses | Everyone |
| Hour 6 | Small usable estate, plan catalogue, demo resource IDs | Persons 2, 3, 4, 5 |
| Hour 12 | Full validated synthetic estate and trace subset | Persons 2 and 3 |
| Hour 28 | Frozen demo fixtures and provenance notes | Everyone |

**Done when:** A clean checkout regenerates the data; every demo resource has traceable metrics and prices; the system needs no cloud credentials to load the estate.

## 2. Person 2 — Demand Forecasting, ML Evaluation, and Scenario Replay

**Goal:** Estimate future resource needs and provide evidence about candidate capacity.

**Own:** `backend/app/ml/`, `experiments/`, feature extraction, forecast artifacts, historical replay, and scenario evaluation. Person 3 owns final plan selection and hard policy decisions.

**Implementation steps**

1. **Define the forecasting and replay interfaces immediately.** Agree with Person 3 on a forecast response containing resource ID, horizon, CPU/memory demand, uncertainty, data coverage, method/version, and observation window. Return explicit insufficient-data results. Supply a fixture response while the models are being built.
2. **Build features from Person 1's data.** Calculate p95, p99, peaks, rolling statistics, lags, daily/weekly time features, missingness, and absolute demand. Keep future observations out of input features.
3. **Deliver deterministic baselines first.** Implement historical rolling-p99 and seasonal-naive estimates. Person 3 can integrate these immediately, allowing the product to work before ML experiments finish.
4. **Time-box CPU experiments to approximately five hours.** Compare the baselines with Ridge and LightGBM quantile regression on a bounded dataset. Cap parallelism for the 8 GB development environment. Add Random Forest only if time remains; defer neural models and extra model families until the core flow passes.
5. **Evaluate chronologically.** Use train/validation/test time windows, a purge gap for overlapping targets, and a separate VM holdout. Report forecast coverage, peak underprediction, pinball loss where applicable, runtime, and memory. With Person 3, also compare unsafe-candidate rates and resulting simulated costs.
6. **Select the validated method.** Use the stronger measured method, including a baseline if it wins. Save model/feature versions and repeatable evaluation results. Do not present teacher-policy labels as proven production-optimal decisions.
7. **Implement candidate replay and stress scenarios.** Accept a proposed capacity from Person 3, replay historical demand, and evaluate traffic growth, batch loads, memory spikes, and network stress. Preserve time patterns with block-based sampling. Return breached constraints, modeled breach frequency, and assumptions; this is not an actual outage probability.
8. **Expose evidence through backend services.** Provide Person 3 with callable forecast/replay functions and Person 5 with versioned evidence records. Supply the results for `GET /api/ml/benchmarks` and the frontend's forecast and scenario panels.

**Handoffs**

| By | Deliverable | Recipient |
| --- | --- | --- |
| Hour 4 | Forecast/replay contracts and fixtures | Persons 3, 4, 5 |
| Hour 12 | Baseline forecasts and data-quality outcomes | Person 3 |
| Hour 20 | Model comparison and selected inference method | Persons 3 and 4 |
| Hour 28 | Replay/scenario results for demo candidates | Persons 3 and 5 |

**Done when:** Forecasting is reproducible, insufficient data causes abstention, model selection has measured support, and unsafe candidate capacities appear in replay evidence.

## 3. Person 3 — Backend APIs, Optimization, Cost Engine, and Policy Gates

**Goal:** Turn inventory and forecasts into explainable recommendations with correct economics and enforceable safety rules.

**Own:** FastAPI application wiring, `backend/app/api/`, `backend/app/engine/`, SQLite metadata/events, recommendation/change schemas, and shared backend authorization and lifecycle enforcement.

**Implementation steps**

1. **Create the backend skeleton and publish contracts.** Deliver health checks, configuration, OpenAPI responses, shared error shapes, and SQLite persistence. Define recommendation, evidence, approval, and change IDs. Freeze initial contracts with the other owners during hours 0–4.
2. **Expose inventory and dashboard APIs.** Connect Person 1's adapter to summary, resource filters, metrics, and plan endpoints. Add recommendation and alert retrieval. Give Person 4 stable responses early, even if the engine initially uses baseline inputs.
3. **Implement deterministic candidate enumeration.** For each resource, compare existing valid plans against absolute demand, forecasts, region, family/architecture, memory, disk, IOPS, network, and dependencies. Return the exact target plan or an explicit reason to keep/defer the current configuration.
4. **Add actions in order.** Start with rightsizing and no-action/insufficient-data outcomes; then add non-production scheduling, idle-resource investigation, and orphan review. Orphan detection creates an ownership-review recommendation, not an automatic deletion.
5. **Build the cost engine once.** Calculate before/after monthly compute, storage, IP, backup, and egress charges with versioned prices and billing assumptions. Show one-time costs separately. Recalculate combined resize/schedule actions so their savings are not counted twice. Separate potential savings, accepted projections, and observed outcomes.
6. **Enforce hard gates and attach validation.** Block incompatible plans, unsafe capacity, prohibited production schedules, stale/missing evidence, unverified ownership, and invalid revisions. Combine Person 2's replay with Person 5's measured benchmark evidence. Record passed, failed, and uncertain checks; the agent cannot bypass them.
7. **Implement simulation, verification, and lifecycle services.** Wire `POST /api/simulate`, `POST /api/verify`, recommendation accept/reject, and change proposal/status APIs. Use the master's lifecycle, keeping approval, dry-run, and applied states distinct. Bind approval to the exact action, resource, configuration, and evidence version; require reapproval after material changes.
8. **Finish integration and core tests.** Test unsafe downsizing, missing data, orphan ownership, plan compatibility, schedule billing, overlapping savings, stale approvals, and unauthorized actions. Supply the same service functions to REST and MCP so neither path has separate business rules.

**Handoffs**

| By | Deliverable | Recipient |
| --- | --- | --- |
| Hour 4 | Running FastAPI skeleton and stable API examples | Persons 4 and 5 |
| Hour 12 | Inventory APIs and baseline recommendations | Persons 4 and 5 |
| Hour 20 | Cost engine, hard gates, simulation, lifecycle services | Persons 4 and 5 |
| Hour 30 | Integrated forecasts, replay, evidence, and change APIs | Everyone |

**Done when:** APIs produce exact plan proposals and defensible cost calculations, unsafe proposals are blocked, and REST/MCP calls obey the same permissions and lifecycle.

## 4. Person 4 — Frontend, Dashboard, Simulation, and Review Experience

**Goal:** Make the complete optimization journey understandable and usable in a short demonstration.

**Own:** `frontend/`, using React, Vite, TypeScript, Tailwind, and Recharts; application navigation, API client, charts, forms, and presentation of evidence.

**Implementation steps**

1. **Build the app shell against agreed fixtures.** Create navigation, shared cards/tables/charts, an API client, and loading, empty, and error states. Organize the experience around Overview → Resources → Recommendations → Simulation/Evidence → Execution, with Copilot and Audit accessible from those views.
2. **Implement Overview and Resource Explorer.** Show spend, potential savings, alerts, region/environment/team filters, resource details, and historical utilization. Clearly label units, time windows, currency, and synthetic data.
3. **Build the Recommendation Center.** Display current and proposed plans, action, monthly cost impact, reason, confidence/uncertainty, risk, and blocking checks. Show no-action and insufficient-data outcomes alongside actionable opportunities.
4. **Add interactive what-if controls.** Let the user change candidate plan, permitted schedule, or traffic multiplier. Send those inputs to the backend simulation API and display recalculated costs and capacity results. Keep authoritative calculations in Person 3's service.
5. **Create the evidence view.** Show forecasts, model comparison, replay outcomes, measured benchmark results, pricing assumptions, ownership, and rollback instructions. Distinguish a passed modeled scenario from a measured benchmark and from post-change verification.
6. **Implement review and change status.** Add accept/reject controls, exact-change approval details, Terraform/runbook downloads, and proposal/dry-run status. Render backend blockers and stale approvals clearly. An approval click must not make the UI claim infrastructure has already changed.
7. **Integrate Copilot, alerts, and audit.** Connect Person 5's agent responses and tool history. Make recommendation/evidence references navigable. Keep optional reports or governance features lightweight until the core journey works.
8. **Polish and verify the demo.** Replace fixture responses with live local APIs by hour 30. Check filters, charts, simulator updates, errors, approval states, and downloads. Run the production build and rehearse the final flow with Person 5.

**Handoffs**

| By | Deliverable | Recipient |
| --- | --- | --- |
| Hour 6 | Navigable shell with fixture-backed views | Everyone |
| Hour 16 | Overview, resources, recommendations connected to APIs | Person 3 |
| Hour 28 | Simulation, evidence, approval, Copilot integration | Persons 3 and 5 |
| Hour 34 | Feature-complete demo UI and successful build | Everyone |

**Done when:** A user can inspect a resource, understand and compare proposals, review evidence, approve the exact change, and inspect its real status without leaving the application.

## 5. Person 5 — MCP Agent, Benchmark Verification, Change Workflow, and Release

**Goal:** Connect the decision engine to an evidence-grounded assistant and a controlled, demonstrable infrastructure proposal workflow.

**Own:** `backend/app/agent/`, `backend/app/mcp/`, `backend/app/execution/`, `infra/`, Docker/k6 benchmarks, integration/release coordination, and demo documentation. Each person still tests and documents their own component.

**Implementation steps**

1. **Set up local integration and one-command startup.** Coordinate Python/frontend dependencies, configuration, `.env.example`, and PowerShell instructions. Keep Docker workloads small for the development machine. Establish a repeatable integration smoke check while the other owners build their modules.
2. **Wrap backend services as MCP tools.** Start with resource/metric lookup, candidate plans, optimization, simulation, risk, and evidence retrieval. Add controlled proposal, Terraform validation, approval-request, and status tools only after Person 3's authorization services exist. Store tool calls, evidence versions, errors, and decisions in the shared audit system.
3. **Build a reproducible agent path.** Demonstrate “Why can this VM be downsized?” through tool calls and an evidence-grounded explanation. Support a deterministic scripted flow without an external LLM; add a configured LLM if available. Missing facts and failed tools must remain visible.
4. **Measure the demo workload.** Run a sample API under baseline and candidate Docker CPU/memory limits, generate traffic with k6, and capture p95 latency, HTTP errors, throttling, OOM events, and restarts. Give Person 3 machine-readable results and provenance. Container measurements support the tested workload; they do not prove identical Utho performance.
5. **Implement one complete proposal path.** Start with an exportable Terraform diff or manual runbook and a local validation workflow. Inspect actual Utho provider behavior before generating executable resize operations. Add GitHub PR creation only with configured authorization. If credentials/provider setup are unavailable, show fixture proposals and mock results explicitly; never call a mocked Terraform plan provider-validated.
6. **Enforce the execution boundary with Person 3.** Recheck approval, ownership, evidence freshness, configuration revision, permissions, and idempotency before controlled actions. Keep cloud apply customer-controlled. Provide rollback prerequisites and post-change checks; mark `APPLIED` or `MONITORED` only when the corresponding real or explicitly simulated event occurs.
7. **Add one control-plane test path if time permits.** Use Floci, LocalStack, or a reproducible API mock for the selected operations. Do not require both emulators. Keep emulator/control-plane checks separate from workload performance benchmarks. Defer Jev/TypeSafe, advanced governance, and additional execution modes until acceptance passes.
8. **Lead the final integration gate during hours 34–38.** Have each owner run their checks, then run backend pytest, the frontend build, MCP permission tests, and the end-to-end local flow. Verify unsafe downsizing, missing-data abstention, orphan review, schedule economics, savings reconciliation, approval binding, audit history, and truthful execution status.
9. **Package and rehearse during hours 38–42.** Collect setup instructions, experiment commands, data/pricing assumptions, architecture, evidence exports, known limitations, and a fallback recording. Freeze the demo dataset and avoid optional feature work once final acceptance starts.

**Shared integration schedule**

| Time | Team checkpoint led by Person 5 |
| --- | --- |
| Hours 0–4 | Agree contracts and demo IDs; all five start in parallel with fixtures |
| Hours 4–12 | Connect generated data → baseline optimizer → dashboard |
| Hours 12–20 | Integrate selected forecasts, costs, policy gates, and simulation |
| Hours 20–28 | Attach replay/benchmark evidence, MCP tools, and change proposals |
| Hours 28–34 | Complete UI/API/agent integration and freeze core scope |
| Hours 34–38 | Run acceptance checks and fix integration failures |
| Hours 38–42 | Final documentation, clean-start rehearsal, demo and recording |

**Final 5–7-minute demo flow**

1. Open the overview and filter the estate to the production API.
2. Inspect its eight-vCPU allocation, workload history, and cost.
3. Show why the two-vCPU candidate fails capacity or benchmark checks.
4. Show the four-vCPU candidate's actual validation outcome and savings assumptions. Present it as verified only if the required checks pass.
5. Ask Copilot to explain the decision using its evidence references.
6. Approve the exact proposal, inspect its Terraform/runbook output and dry-run status, and open the audit trail.
7. Briefly show the development schedule, orphan ownership review, insufficient-data case, and anomaly alert.

**Done when:** A clean local startup supports the full demonstration, tool calls and proposals are auditable, validation claims match available evidence, and no unapproved infrastructure mutation is possible.
