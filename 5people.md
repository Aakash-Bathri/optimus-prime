# CloudPilot — Five-Person Implementation Plan

Based on [CLOUDPILOT_MASTER_SPEC.md](CLOUDPILOT_MASTER_SPEC.md). This plan replaces its four-person allocation with **five implementation owners**, within the same **40–42-hour window**. Each numbered section belongs to one person; the steps inside it are in implementation order. The official Utho brief (pages 44–47 of the problem-statements PDF) defines required coverage. This plan governs the five-person allocation, delivery priorities, and acceptance checks; broader master-spec ideas remain optional unless scheduled here.

**Product flow:** Collect data → forecast demand → select a valid plan and calculate savings → validate the proposal → explain and display evidence → obtain approval → prepare a change → monitor the outcome.

**Working rule:** Get one complete local workflow running before adding optional integrations. The application must run without cloud credentials or paid infrastructure. Synthetic data, modeled outcomes, measured benchmarks, dry runs, and live changes must have distinct labels. A written feature or a fixture response is not evidence of a working implementation.

**Delivery priorities:** P0 is every Utho must-have and expected deliverable in the acceptance matrix below. P1 is the agreed differentiation: what-if simulation, evidence-grounded explanations, exports, then one measured benchmark and a controlled proposal path. MCP expands the explanation/proposal path after core integration. P2 is the remaining bonus work and external integrations. If P0 slips, move P1/P2 work out of the demo and record it as deferred; do not cut alerts, required telemetry, cleanup proposals, cost reconciliation, or documentation.

**Integration contract:** By hour 4, commit shared JSON examples and typed schemas for resources, metrics, plans/prices, recommendations, alerts, cost summaries, evidence, approvals, and changes. Every response carries relevant units, currency, UTC timestamps, observation window, and source/version. Workload schedules have an explicit timezone (Asia/Kolkata for the demo). Person 3 coordinates contract changes; affected owners update fixtures and clients together. Backend services own all calculations; REST, UI, and MCP use those same services.

## 1. Person 1 — Data Foundation, Provider Catalogue, and Ingestion

**Goal:** Give every other person consistent, reproducible resource, telemetry, dependency, and pricing data.

**Own:** `data/`, `backend/app/adapters/`, data ingestion, Parquet/DuckDB datasets, and the resource/metric/catalogue schemas in `backend/app/models/`.

**Implementation steps**

1. **Lead the shared contract meeting during hours 0–2.** All five people agree on IDs, units, UTC timestamps, currency, API response shapes, and version fields. Person 3 owns the FastAPI application and recommendation/change schemas; you own the source-data schemas. Commit small JSON examples immediately so the frontend and agent can start with fixtures.
2. **Define the complete required data records.** Inventory includes `resource_id`, `name`, `type` (VM/block volume/public IP), `region`, `environment` (prod/staging/dev), `owner` or `team`, allocated `vcpu`, `ram_gib`, `disk_size_gib`, and `created_at`. Add criticality, management type, dependencies, and provenance. Fields that do not apply to a volume/IP are explicitly null with a reason. Telemetry includes `resource_id`, UTC `timestamp`, `cpu_pct`, `memory_pct`, `disk_used_gib` (plus disk usage %), `disk_read_iops`, `disk_write_iops`, `network_in_bytes_per_second`, and `network_out_bytes_per_second`, with units and quality flags. Keep CPU demand in cores and memory demand in GiB alongside percentages. Distinguish disk throughput from IOPS and occupied disk space. Prices include a per-resource or per-plan hourly/monthly rate, currency, billing rules, and version.
3. **Generate the synthetic estate.** Use a fixed seed to create 120 VMs across **Noida, Bangalore, and Mumbai**, with prod/staging/dev resources and multiple teams. Generate 30 complete days of 15-minute telemetry: exactly 345,600 timestamped VM rows. Mark selected metric values unavailable for the insufficient-data fixture while retaining the regular timestamp grid; coverage checks must use usable values, not row count alone. Add volumes, IPs, dependencies, and six-month billing snapshots separately, including an explicitly synthetic 40% bill increase. Include steady-low, short daily burst peaks, batch, dev-idle-on-weekends, memory-bound, network-bound, and insufficient-data workloads. Preserve short peaks in generation/aggregation so 15-minute averages cannot hide them.
4. **Create the demo fixtures deliberately.** Include an eight-vCPU production API with two- and four-vCPU candidates; a development off-hours/weekend schedule; an idle VM eligible for a proposed stop; a confirmed unused resource eligible for a proposed delete; an unattached volume and an unused public IP; an unknown-owner cleanup case that remains blocked; and missing telemetry. Supply separate cases for a usage spike, sudden cost increase, rising capacity demand, and projected budget overrun, plus a normal control case. Set budgets and dependencies explicitly. Coordinate expected outcomes with Persons 2 and 3; derive results from inputs instead of hardcoding success.
5. **Build a versioned plan and pricing catalogue.** Store region availability, capacity, compatibility, compute/storage/IP charges, billing rules, currency, source, and effective date. Label fixture prices as illustrative. Before claiming real Utho savings, verify current prices, plan IDs, and billing behavior from provider sources.
6. **Implement ingestion behind a common adapter interface.** Deliver the synthetic adapter first. Once required data validation passes, add a bounded public-trace import for Person 2 if time permits, preserving attribution and metric semantics. For example, throughput must not be silently treated as disk capacity or IOPS. Add read-only Utho ingestion only if credentials and time permit.
7. **Validate and package the data.** Check all required fields, exact record count and time range, duplicate timestamps, units, realistic value ranges, missingness, resource references, plan references, and catalogue versions. Show that each region/environment/team filter has data and each fixture is reproducible. Supply one repeatable generation/import command, `docs/data_dictionary.md`, and the data-generation/provenance sections of `docs/assumptions.md`.

**Handoffs**

| By | Deliverable | Recipient |
| --- | --- | --- |
| Hour 2 | Agreed schemas and sample JSON responses | Everyone |
| Hour 6 | Small estate, plan catalogue, all action/alert fixture IDs | Persons 2, 3, 4, 5 |
| Hour 12 | Full validated synthetic estate; public-trace subset if ready | Persons 2 and 3 |
| Hour 28 | Frozen demo fixtures and provenance notes | Everyone |

**Done when:** A clean checkout regenerates the data; required fields, 30-day coverage, 345,600 rows, regions, environments, workload patterns, volumes and IPs pass validation; unavailable values trigger the intended data-quality outcome; every demo resource has traceable metrics and prices; no cloud credentials are needed.

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
8. **Expose evidence through backend services.** Provide Person 3 with callable forecast/replay functions and Person 5 with versioned evidence records. Supply results for `GET /api/ml/benchmarks` and forecast/scenario panels. Document model thresholds, uncertainty, replay simplifications, and limitations in `docs/assumptions.md`. A short-horizon capacity forecast does not fulfill the separate 30–90-day forecasting bonus.
9. **Own long-range forecasting only after the P0 gate passes.** For the optional bonus, provide 30-, 60-, and 90-day daily usage and cost projections with uncertainty and declared growth, scheduling, and pricing assumptions; Persons 3 and 4 handle cost conversion and visualization. Backtest only horizons supported by available history. With only 30 days of telemetry, label longer projections as scenario-based and avoid unsupported accuracy claims.

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
2. **Expose inventory and dashboard APIs.** Connect Person 1's adapter to summary, region/environment/team filters, per-resource history, and plan endpoints. Publish recommendation, explained-alert, and cost-summary retrieval. Give Person 4 stable responses early, even if the engine initially uses baseline inputs.
3. **Implement deterministic candidate enumeration.** For each resource, compare existing valid plans against absolute demand, forecasts, region, family/architecture, memory, disk, IOPS, network, and dependencies. Return the exact target plan or an explicit reason to keep/defer the current configuration.
4. **Implement every required recommendation action.** Start with resize and no-action/insufficient-data outcomes, then implement `schedule_stop_start`, `stop_idle`, `delete_idle`, `cleanup_volume`, and `release_ip` proposals. Each includes action, exact resource/target configuration, reason, estimated monthly saving, risk/confidence, evidence, prerequisites, and approval status. Unknown ownership or unresolved dependencies produce blocked/review outcomes; confirmed safe fixtures must also demonstrate actionable cleanup proposals. Provide exports or dry runs for stop/delete/cleanup; live cloud mutation is not required. State irreversible deletion consequences and backup requirements; never claim every delete is reversible.
5. **Build the cost engine once.** Calculate before/after monthly compute, storage, IP, backup, and egress charges with versioned prices and billing assumptions. Return current cost, projected cost, and monthly saving **per recommendation, per environment (prod/staging/dev), and for the entire estate**. The accepted projection applies only accepted, compatible actions; rejecting or undoing acceptance restores the corresponding totals. Recalculate combined resize/schedule actions from their resulting bill rather than adding independent savings. Prevent conflicting stop/delete/resize actions on the same resource. Show one-time costs separately and separate potential, accepted projected, and observed savings. Document billable hours, rounding, fixed charges, stopped-instance charges, and orphan-resource environment attribution. Use clearly labeled illustrative pricing when real prices are unavailable.
6. **Enforce hard gates and attach validation.** Block incompatible plans, unsafe capacity, prohibited production schedules, stale/missing evidence, unverified ownership, and invalid revisions. Attach Person 2's replay and, when available, Person 5's measured benchmark evidence. Missing optional benchmark results remain explicitly unavailable; only describe a configuration as benchmark-verified after that benchmark runs and passes. Record passed, failed, and uncertain checks; the agent cannot bypass them.
7. **Implement simulation, verification, and lifecycle services.** Wire `POST /api/simulate`, `POST /api/verify`, recommendation accept/reject, and change proposal/status APIs. Use the master's lifecycle, keeping approval, dry-run, and applied states distinct. Bind approval to the exact action, resource, configuration, and evidence version; require reapproval after material changes.
8. **Build alert detection, not just alert endpoints.** Own four rule families: unusual usage spikes, sudden cost increases, approaching CPU/memory/disk/network capacity, and projected budget overruns. Use documented configurable thresholds and history windows. A simple month-to-date spend plus remaining-days run-rate projection can satisfy budget alerts; the 30–90-day ML bonus is not a dependency. Each alert includes resource/scope, category, severity, timestamp, observed value, baseline/threshold, units, explanation, and provenance. Detect cost changes from actual modeled billing changes rather than assuming every utilization spike increases fixed-plan charges. Test one positive fixture per family and a normal control.
9. **Finish integration and core tests.** Test unsafe peak/memory downsizing, missing data, all action types, unknown-owner blocking, plan compatibility, schedule billing, overlapping/conflicting actions, all four alert families, stale approvals, and unauthorized actions. Verify per-environment sums equal estate totals before/after accept/reject and remain correct after refresh. Supply the same service functions to REST and MCP. Own pricing, policy/alert thresholds, and cost simplifications in `docs/assumptions.md`.

**Handoffs**

| By | Deliverable | Recipient |
| --- | --- | --- |
| Hour 4 | Running FastAPI skeleton and stable API examples | Persons 4 and 5 |
| Hour 12 | Inventory APIs and baseline recommendations | Persons 4 and 5 |
| Hour 20 | All action proposals, environment/estate costs, four alert detectors, hard gates and lifecycle | Persons 4 and 5 |
| Hour 30 | Integrated forecasts, replay, evidence, and change APIs | Everyone |

**Done when:** APIs produce all required action proposals, explained alerts in all four categories, and reconciled per-recommendation/environment/estate costs; unsafe proposals are blocked; accept/reject updates persist; REST/MCP obey the same permissions and lifecycle.

## 4. Person 4 — Frontend, Dashboard, Simulation, and Review Experience

**Goal:** Make the complete optimization journey understandable and usable in a short demonstration.

**Own:** `frontend/`, using React, Vite, TypeScript, Tailwind, and Recharts; application navigation, API client, charts, forms, and presentation of evidence.

**Implementation steps**

1. **Build the app shell against agreed fixtures.** Create navigation, shared cards/tables/charts, an API client, and loading, empty, and error states. Organize the experience around Overview → Resources → Recommendations → Simulation/Evidence → Execution, with Copilot and Audit accessible from those views.
2. **Implement Overview and Resource Explorer.** Show CPU, memory, storage usage/IOPS, and separate network in/out across the estate and in each resource's 30-day history. Provide region/environment/team filters and inventory details including creation date. Show current/projected spend and monthly savings for prod, staging, dev and the estate, plus explained alerts. Label units, time windows, currency, data gaps and synthetic sources; show unavailable metrics explicitly.
3. **Build the Recommendation Center.** Display current/proposed configuration, action, monthly saving, reason, confidence/uncertainty, risk, and blocking checks. Include resize, idle stop/delete, orphan volume/IP cleanup and off-hours schedule cards, plus no-action and insufficient-data outcomes. On accept/reject, retrieve authoritative recalculated per-recommendation, per-environment and total costs immediately; handle backend conflicts without optimistic false savings.
4. **Add interactive what-if controls.** Let the user change candidate plan, permitted schedule, or traffic multiplier. Send those inputs to the backend simulation API and display recalculated costs and capacity results. Keep authoritative calculations in Person 3's service.
5. **Create the evidence view.** Show forecasts, model comparison, replay outcomes, measured benchmark results, pricing assumptions, ownership, and rollback instructions. Distinguish a passed modeled scenario from a measured benchmark and from post-change verification.
6. **Implement review and change status.** Add accept/reject controls, exact-change approval details, Terraform/runbook downloads, and proposal/dry-run status. Render backend blockers and stale approvals clearly. An approval click must not make the UI claim infrastructure has already changed.
7. **Integrate Copilot, alerts, and audit.** Display all four alert categories with the trigger value, comparison and explanation. Connect Person 5's agent responses and tool history; make recommendation/evidence references navigable. Keep optional reports or governance features lightweight until the core journey works.
8. **Polish and verify the demo.** Replace fixture responses with live local APIs by hour 30. Check all filters and metric histories, recommendation coverage, per-environment totals after accept/reject, all four explained alerts, simulator updates, errors, approval states, downloads, and state after refresh. Run the production build and rehearse the final flow with Person 5. Implement optional long-range forecasts or role/sustainability views only after core acceptance passes.

**Handoffs**

| By | Deliverable | Recipient |
| --- | --- | --- |
| Hour 6 | Navigable shell with fixture-backed views | Everyone |
| Hour 16 | Overview, resources, recommendations connected to APIs | Person 3 |
| Hour 28 | Complete core UI; simulation/evidence/approval/Copilot as P1 permits | Persons 3 and 5 |
| Hour 34 | Feature-complete demo UI and successful build | Everyone |

**Done when:** A user can inspect every required metric, filter the estate, understand all required recommendation types, accept/reject and see reconciled environment/estate totals, understand four alert types, review evidence, approve the exact change, and inspect truthful status without leaving the application.

## 5. Person 5 — MCP Agent, Benchmark Verification, Change Workflow, and Release

**Goal:** Connect the decision engine to an evidence-grounded assistant and a controlled, demonstrable infrastructure proposal workflow.

**Own:** `backend/app/agent/`, `backend/app/mcp/`, `backend/app/execution/`, `infra/`, Docker/k6 benchmarks, integration/release coordination, and demo documentation. Each person still tests and documents their own component.

**Implementation steps**

1. **Set up local integration, documentation, and one-command startup first.** Own the root `README.md`, configuration, `.env.example`, pinned dependency setup, generation/start commands, and PowerShell instructions. Require a clean checkout to run without paid services, cloud credentials, an LLM key, or Docker; Docker benchmarks remain a separate workflow. Create `docs/assumptions.md` with named contributions from Persons 1–3, plus `docs/architecture.md`, `docs/demo_script.md`, and `docs/acceptance.md`. Establish a repeatable core integration smoke check before building MCP or provider integrations.
2. **Build a reproducible agent path.** Demonstrate “Why can this VM be downsized?” through tool calls and an evidence-grounded explanation. Support a deterministic scripted flow without an external LLM; add a configured LLM if available. Missing facts and failed tools must remain visible.
3. **Implement one complete proposal path.** Start with an exportable Terraform diff or manual runbook and a local validation workflow. Inspect actual Utho provider behavior before generating executable resize operations. Add GitHub PR creation only with configured authorization. If credentials/provider setup are unavailable, show fixture proposals and mock results explicitly; never call a mocked Terraform plan provider-validated.
4. **Enforce the execution boundary with Person 3.** Recheck approval, ownership, evidence freshness, configuration revision, permissions, and idempotency before controlled actions. Keep cloud apply customer-controlled. Provide rollback prerequisites and post-change checks; mark `APPLIED` or `MONITORED` only when the corresponding real or explicitly simulated event occurs.
5. **Measure the demo workload.** Run a sample API under baseline and candidate Docker CPU/memory limits, generate traffic with k6, and capture p95 latency, HTTP errors, throttling, OOM events, and restarts. Give Person 3 machine-readable results and provenance. Container measurements support the tested workload; they do not prove identical Utho performance.
6. **Wrap backend services as MCP tools.** Start with resource/metric lookup, candidate plans, optimization, simulation, risk, and evidence retrieval. Add controlled proposal, Terraform validation, approval-request, and status tools only after Person 3's authorization services exist. Store tool calls, evidence versions, errors, and decisions in the shared audit system.
7. **Add one control-plane test path if time permits.** Use Floci, LocalStack, or a reproducible API mock for the selected operations. Do not require both emulators. Keep emulator/control-plane checks separate from workload performance benchmarks. Defer Jev/TypeSafe, advanced governance, and additional execution modes until acceptance passes.
8. **Lead a P0 gate by hour 30 and final integration during hours 34–38.** Use the acceptance matrix below; record results and evidence in `docs/acceptance.md` as planned/passed/failed/deferred, without marking unexecuted checks passed. Have each owner run their checks, then run backend pytest, the frontend build, relevant MCP permission tests, and the end-to-end local flow. Verify complete telemetry, all actions and four alert families, unsafe downsizing, missing-data abstention, orphan ownership, schedule economics, environment/estate savings reconciliation, approval binding, audit history, and truthful status. If core fails, redirect remaining optional effort to P0 fixes.
9. **Package and rehearse during hours 38–42.** Verify `docs/assumptions.md` explicitly covers pricing and billing, rightsizing/idle/alert/data-quality thresholds, data generation, and simplifications (forecasting, CPU scaling, hardware, absent metrics, carbon if shown). Link the sheet, architecture, experiment commands, acceptance results and limitations from the README. Rehearse the timed demo below, covering the problem, walkthrough, architecture and real-world impact; capture a fallback recording. Every owner must explain their own module, assumptions and results. Freeze demo fixtures and optional work once final acceptance starts.

**Shared integration schedule**

| Time | Team checkpoint led by Person 5 |
| --- | --- |
| Hours 0–4 | Agree contracts and demo IDs; all five start in parallel with fixtures |
| Hours 4–12 | Connect generated data → baseline optimizer → dashboard |
| Hours 12–20 | Integrate forecasts, all required actions, environment costs, four alert families and policy gates |
| Hours 20–28 | Finish P0 end-to-end checks first; attach replay, then benchmark/MCP/proposal differentiation |
| Hours 28–34 | P0 gate by hour 30; complete integration and freeze scope by hour 34 |
| Hours 34–38 | Run acceptance checks and fix integration failures |
| Hours 38–42 | Final documentation, clean-start rehearsal, demo and recording |

**Final 5–7-minute demo flow**

| Time | Demonstration |
| --- | --- |
| 0:00–0:35 | State the problem: 120 VMs across three regions/environments, a growing bill, and peak-load risk. Label the synthetic scenario. |
| 0:35–1:15 | Show the dashboard, region/environment/team filters, required utilization metrics and a resource's history. |
| 1:15–2:25 | Inspect the eight-vCPU API; show why the two-vCPU candidate fails and the actual outcome of the four-vCPU checks. Explain reason, risk and savings assumptions. |
| 2:25–3:15 | Accept/reject a recommendation and show current/projected/saved amounts updating per environment and in total. Preview a dev off-hours schedule. |
| 3:15–4:10 | Show idle stop/delete proposals, both orphan volume and IP cleanup, an unknown-owner blocker, and missing-data abstention. |
| 4:10–4:45 | Show all four explained alert categories, including capacity and budget projections. |
| 4:45–5:30 | Explain architecture: ingestion → forecast/rules → plan/cost engine → safety/evidence → API/UI. Show a rule-based or Copilot explanation and one export/dry-run if ready. |
| 5:30–6:30 | State real-world impact using computed modeled monthly savings, remaining risk and assumptions; distinguish these from realized savings. Show setup, acceptance evidence and known limitations. |

Rehearse to approximately 6½ minutes. Optional integrations must fit inside their allocated segment; do not omit a must-have to show them.

**Done when:** A clean local startup supports the full demonstration, tool calls and proposals are auditable, validation claims match available evidence, and no unapproved infrastructure mutation is possible.


## Shared Utho Must-Have Acceptance Matrix

This matrix closes coverage gaps in the work allocation. Owners implement and verify each item; Person 5 records the actual result and evidence. It describes required future work, not completed software.

| ID | Requirement / deliverable | Implementation owner | Acceptance evidence |
| --- | --- | --- | --- |
| U01 | Required inventory, 30-day CPU/memory/disk/IOPS/network telemetry and hourly/monthly pricing | Person 1 | Schema/data validation checks required fields, units, 120 VMs, 345,600 rows, coverage and explicitly unavailable values. |
| U02 | Noida/Bangalore/Mumbai; prod/staging/dev; realistic low, burst, batch, weekend-idle, orphan and anomaly cases | Person 1 | Fixture manifest identifies resource IDs, workloads, both unattached volume and unused IP, four alert cases and a normal control. |
| U03 | CPU/memory/storage/network dashboard, region/environment/team filters and resource history | Person 4; Person 3 APIs | Demonstrate combined filters and all metric histories against local generated data; include empty/error/data-gap states. |
| U04 | Peak-aware rightsizing of over-provisioned/underutilized/idle resources with specific target configuration | Person 3; Person 2 evidence | Low-average/high-peak and memory-bound candidates are blocked; compatible safe fixture has a concrete target plan and traceable rationale. |
| U05 | Resize, idle stop/delete, orphan volume/IP cleanup and off-hours scheduling recommendations | Person 3; Person 4 UI | Each action has a sample card/export with action, reason, monthly saving and risk/confidence; unknown owner/dependency blocks unsafe proposals. Live deletion is unnecessary. |
| U06 | Before/after monthly cost and savings per recommendation, per environment and total; live accept/reject updates | Person 3; Person 4 UI | Accept, reject, undo and refresh reconcile all totals; combined resize/schedule and conflicting actions cannot double-count savings; stopped-resource charges follow stated rules. |
| U07 | Explained usage-spike, cost-increase, capacity-trend and projected-budget alerts | Person 3; Person 1 fixtures; Person 4 UI | Four positive cases and a normal control exercise detectors; UI shows timestamp, trigger, baseline/threshold and explanation. |
| U08 | Working local/free prototype, utilization dashboard and recommendation engine with sample calculations | All; Person 5 coordinates | Clean-checkout generation/start succeeds without paid services or credentials; representative savings can be reproduced from versioned inputs. |
| U09 | Assumptions sheet: pricing, thresholds, data-generation logic and simplifications | Persons 1–3; Person 5 assembles | `docs/assumptions.md` contains all four categories and is linked from README and cost/evidence views. |
| U10 | Source repository and README setup steps | Person 5; all module owners | README covers prerequisites, install, seed, start, test/build, optional integrations and troubleshooting; another contributor follows it from a clean checkout. |
| U11 | 5–7-minute video/live demo of problem, walkthrough, technical architecture and real-world impact | Person 5; everyone rehearses | Timed script/recording covers all four topics and uses calculated, assumption-labeled savings; team can explain every component. |
| U12 | Transparent cost assumptions, safety and technical verification | All; Person 5 records | Backend checks and frontend build pass; screenshots/commands/results are linked in `docs/acceptance.md`; modeled, measured and realized outcomes are distinguished. |

**Release gate:** Every U01–U12 item must pass before claiming Utho core compliance. Failed checks remain visible with an owner and fix; P1/P2 deferrals do not count as P0 completion. Safety/effectiveness (25%), implementation (20%) and transparent cost estimates (20%) account for 65% of the judging weight and receive first priority.

## Bonus Coverage and Scope Control

All six official bonuses have explicit owners below. Their optional status is intentional; mark each implemented, partial or deferred in the final README. Extra master-spec features do not silently become hackathon commitments.

| Official bonus | Owner / supporting owners | Priority and acceptance |
| --- | --- | --- |
| What-if simulator | Person 3 + Person 4 | P1: preview a dev 20:00–08:00 Asia/Kolkata shutdown schedule, candidate changes and traffic scenarios with backend-derived costs and policy results. |
| Plain-language explanations, LLM or rule-based | Person 5 + Persons 3/4 | P1: explain action, evidence, risk and savings without invented values; deterministic explanation works without an LLM key. MCP/LLM is an optional extension. |
| Export recommendations as report, script or IaC | Person 5 + Persons 3/4 | P1: downloadable Markdown/CSV report or script/IaC with exact action, prices, assumptions and prerequisites. Real GitHub PR/provider access is optional. |
| Cost and usage forecasts for 30–90 days | Person 2 + Persons 3/4 | P2: explicit 30/60/90-day projections, uncertainty, assumptions and available backtest evidence; do not substitute next-hour capacity forecasts. |
| Sustainability/energy and carbon view | Person 2 model + Person 3 aggregation + Person 4 UI | P2: show estimated before/after energy and carbon using documented power, utilization, region-factor source/date and uncertainty assumptions. Use illustrative factors if needed and label them; no fabricated measured emissions. |
| Multi-tenant or role-based views | Person 3 authorization + Person 4 UI | P2: choose engineer/finance/leadership views instead of full multitenancy. Define visible data and permitted actions; if permissions are claimed, enforce them on the backend and verify an unauthorized request is rejected. |

**Optional integration order for Person 5:** core startup/docs/release checks → basic explanation/export → one measured Docker/k6 benchmark and local proposal → MCP wrapper → configured GitHub/Utho adapter or one API mock/emulator. Choose tasks that fit remaining time. Floci/LocalStack, Jev/TypeSafe, public-trace expansion, paid APIs, extra models and autonomous apply are not Utho must-haves. Record absent benchmark/provider evidence honestly; never label an unrun or mocked check as verified.
