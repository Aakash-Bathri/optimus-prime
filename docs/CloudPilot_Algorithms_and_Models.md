# CloudPilot SmartCloud Optimizer: Algorithms and Models by Architecture Layer

This document maps the improved CloudPilot architecture to practical algorithms, statistical methods, and machine-learning models. It prioritizes a safe, explainable Utho-specific optimizer that can be tested against historical telemetry.

## Recommended design principles

- **Start deterministic:** use rules, statistical summaries, hard constraints, and candidate enumeration before introducing complex ML or mathematical solvers.
- **Keep prediction separate from decisions:** forecasting estimates demand; the constraint-based optimizer decides which candidate configurations are eligible.
- **Treat safety as a hard constraint:** a low predicted cost must never override compatibility, capacity, policy, or data-quality failures.
- **Make results reproducible:** record input data versions, catalog/pricing versions, thresholds, model versions, and recommendation evidence.
- **Separate estimated from verified savings:** a modelled saving is not proof that a change was applied or that the saving was realized.
- **Use only verified provider data:** do not invent Utho plans, prices, capabilities, or APIs. If critical information is missing, abstain or mark the recommendation non-actionable.

## Algorithms and models table

| Architecture layer | Goal | Recommended algorithms / models | Alternatives / later upgrades | Inputs | Outputs | Priority |
|---|---|---|---|---|---|---|
| **1. Input data and validation** | Ensure inventory, telemetry, and prices are usable | Pydantic or JSON Schema validation; deterministic range/consistency checks; freshness and coverage checks; missingness reports; catalog/pricing version IDs | Pandera or Great Expectations for larger tabular pipelines; distribution drift checks | Inventory, CPU/RAM time series, dependencies, catalog, prices, timestamps | Validated records, quality flags, reason codes, lineage | **P0 — required** |
| **2. Policy and eligibility gate** | Decide which resources/actions may be considered | Deterministic rule engine; allow/deny lists; policy predicates; state-machine validation; fail-closed checks for missing critical facts | OPA/Rego if policies become complex or need central governance | Ownership, tags, environment, resource state, policy configuration, data-quality flags | Eligible resources/actions, exclusions, blocking reasons | **P0 — required** |
| **3. Statistical engine** | Summarize historical utilization and characterize load | Rolling mean/median; P50/P95/P99 quantiles; maximum; rolling windows; EWMA for trends; MAD for robust outlier detection; missing-data and coverage statistics | Seasonal decomposition; change-point detection if regime changes matter | CPU/RAM/disk/network metrics, timestamps, workload metadata | Baselines, peak summaries, trend/outlier flags, data sufficiency | **P0 — required** |
| **4. Forecasting engine** | Estimate future demand and uncertainty | Start with seasonal-naive (same time yesterday/week) and rolling-quantile baselines; Ridge regression with lag/time features; LightGBM quantile regression if enough representative data exists | Random Forest or gradient boosting; probabilistic time-series models if justified by evaluation | Historical metrics, lagged values, hour/day features, schedules, optional external signals | Forecast horizon, P50/P90/P95 demand estimates, intervals/uncertainty, baseline comparison | **P1 — after baseline metrics** |
| **5. Candidate generation and Utho compatibility** | Generate only provider-supported alternatives compatible with workload | Deterministic catalog filtering; hard predicates over vCPU/RAM, architecture, storage, region/availability and known workload requirements; compatibility states `known / unknown / incompatible` | Versioned capability rules; provider API sync only where an official supported API is verified | Current specification, verified Utho catalog, workload constraints, region, policy | Feasible candidates with rejection reasons and catalog version | **P0 — required** |
| **6. Cost and pricing engine** | Compare candidate costs consistently | Decimal-based arithmetic; deterministic price calculation; versioned price snapshots; billing-period normalization; current-vs-candidate total-cost calculation; sensitivity analysis for uncertain charges | Cost ranges; reconciliation against actual invoices when available | Verified prices, configuration, billing rules, discounts/fees/taxes where applicable | Current cost, candidate cost, modeled net savings, assumptions and price provenance | **P0 — required** |
| **7. Constraint-based optimizer** | Select the lowest-cost candidate satisfying hard requirements | Deterministic candidate enumeration; filter hard constraints, project utilization, calculate cost, rank eligible candidates by net cost/savings; deterministic tie-breaking | OR-Tools/CP-SAT or MILP only if joint multi-resource decisions later add measurable value | Feasible candidates, projected demand, safety thresholds, costs, policies | Selected plan or explicit abstention; alternatives; constraint results; rationale | **P0 — required** |
| **8. Rightsizing load projection** | Estimate how demand might behave on another plan | First-order capacity-ratio projection: `projected_utilization = current_utilization × current_capacity / target_capacity`; evaluate P95/P99 and peaks separately; enforce configured headroom | Calibrate against observed post-resize outcomes or workload benchmarks | Current capacity, utilization distribution, target capacity, safety thresholds | Projected target utilization, safety checks, caveats | **P0 — required** |
| **9. Simulation and historical replay** | Test recommendations before presenting them as safe | Deterministic replay over historical windows; peak/stress scenarios; backtesting; scenario analysis; moving-block bootstrap for uncertainty if enough time-series data exists | Workload-specific discrete-event simulation if resource interactions require it | Historical metrics, candidates, constraints, price snapshot, scenario definitions | Constraint violations, eligible-candidate rate, modeled savings, stress results, uncertainty ranges | **P0 — required for validation** |
| **10. Recommendation evidence and explanation** | Make results auditable and understandable | Structured evidence object; deterministic reason codes; rule trace; metric/price provenance; templated explanation from structured facts | LLM-assisted explanation only as a presentation layer; validate numeric claims against structured outputs | Statistics, candidate evaluations, prices, constraints, data-quality flags | Recommendation, rationale, risks, assumptions, source versions, rejected alternatives | **P0 — required** |
| **11. Approval and action governance** | Prevent unintended or unsafe changes | Explicit approval workflow; role-based access control; idempotency keys; state-machine transitions; dry-run by default; audit logging; revalidation before action | Policy-as-code and staged rollout/canary workflow if automation is introduced | Recommendation, actor/role, approval policy, latest resource state | Approved/rejected action request, audit record, execution eligibility | **P0 — required** |
| **12. Recommendation lifecycle and savings verification** | Track what happened after a recommendation was issued | Snapshot-and-diff; deterministic lifecycle state machine; compare before/after configurations; reconcile modeled savings against actual billing when available | Cohort analysis or causal impact methods if enough comparable data exists | Recommendation history, inventory, action/audit logs, actual bills if available | Applied/dismissed/expired status; estimated, unverified, and verified savings kept separate | **P0 — required** |
| **13. Feedback control and calibration** | Check whether predictions and safety margins remain reliable | Forecast residuals; MAE/RMSE and quantile loss; EWMA of residuals; threshold alerts; periodic recalibration after enough verified outcomes | Online learning only with monitoring and rollback; avoid reinforcement learning initially | Forecasts, actual metrics, applied changes, verified outcomes | Calibration warnings, updated thresholds/model version, feedback report | **P1 — after outcome data exists** |
| **14. Idle-resource detection** | Find likely unused or underused resources | Rules over sustained low utilization; minimum observation window; active-hours/seasonality checks; owner/dependency checks; data coverage checks | Change-point detection or anomaly detection as supporting signals, never sole deletion criteria | CPU/RAM/network/disk activity, resource state, ownership, dependencies | Candidate idle resources with evidence and caveats | **P1 — separate scenario** |
| **15. Scheduling optimization** | Estimate savings from stopping resources outside usage windows | Calendar/time-window rules; hourly/daily usage-pattern aggregation; schedule simulation; cost calculation with startup/shutdown and persistence constraints | Forecast-based schedule suggestions after reliable history exists | Historical usage, operating schedule, dependencies, downtime policy, billing rules | Suggested schedule, estimated savings, availability risks | **P1 — separate scenario** |
| **16. Bottleneck analysis** | Detect resource pressure as well as excess capacity | Threshold rules plus correlated CPU, memory, disk I/O, network and latency signals; rolling trend analysis; change-point detection where useful | Supervised classification if labeled incident/outcome data becomes available | Multivariate telemetry, latency/error metrics if available, events | Bottleneck hypothesis, supporting evidence, confidence/unknowns | **P2 — depends on telemetry** |
| **17. GPU optimization** | Identify GPU underutilization or capacity mismatch | Rules and quantiles for GPU utilization, memory, duty cycle and workload activity; compatible-device filtering; GPU-specific cost calculation | Forecasting or workload-specific benchmarking if adequate GPU telemetry exists | Verified GPU inventory/catalog, utilization, memory, workload constraints, pricing | Candidate recommendations with compatibility and evidence | **P2 — only with reliable GPU data** |
| **18. Storage optimization** | Find storage savings without data-loss or retrieval risks | Lifecycle rules; size/access-frequency analysis; total-cost model including requests, retrieval, monitoring and transfer; metadata-based duplicate candidate grouping where supported | Content hashing only when justified and permitted; workload-specific lifecycle prediction | Storage inventory, size, access metrics, object metadata, verified pricing and policies | Tiering/cleanup/deduplication candidates and net-cost estimates | **P2 — requires provider support** |
| **19. Network-cost analysis** | Identify expensive traffic paths and egress opportunities | Aggregations by source/destination/region/traffic class; deterministic tariff calculation; anomaly detection for unusual traffic changes | Graph-based traffic analysis if topology and flow records are available | Flow/egress metrics, topology, verified tariffs | Cost breakdown, anomalies, possible actions | **P2 — requires network data** |
| **20. Monitoring and evaluation** | Measure optimizer quality and prevent regressions | Unit/property tests; historical replay; regression tests; benchmark scenarios; track false-positive rate, constraint violations, eligible-candidate rate, forecast error and savings-estimation error | Shadow mode and controlled rollout for future automated action | Test fixtures, historical datasets, decisions, outcomes | Evaluation report, regression alerts, release gate | **P0 — continuous** |

## Suggested model choices by phase

| Phase | Build | Recommended approach | Why |
|---|---|---|---|
| **Phase 1: Safe MVP** | Validation, statistics, catalog matching, cost engine, rightsizing, evidence | Rules + quantiles + deterministic candidate enumeration | Explainable, reproducible, straightforward to test |
| **Phase 2: Better demand estimates** | Forecasting and schedule suggestions | Seasonal-naive baseline, then Ridge; evaluate LightGBM quantile regression if data supports it | Adds predictive value without making ML the decision-maker |
| **Phase 3: Prove results** | Historical replay, lifecycle and savings verification | Backtesting, snapshot-and-diff, billing reconciliation | Shows whether recommendations were safe and financially useful |
| **Phase 4: Specialized scenarios** | Idle, GPU, storage, network and bottleneck modules | Scenario-specific rules/statistics, then models only where labeled data and measurable benefit exist | Avoids adding complexity without evidence |

## Evaluation metrics to track

| Area | Metrics |
|---|---|
| Data quality | Telemetry coverage, freshness, missing-value rate, catalog/pricing validity |
| Forecasting | MAE/RMSE; pinball (quantile) loss for quantile forecasts; prediction-interval coverage |
| Optimization safety | Hard-constraint violation count; projected/observed capacity breaches; replay failure rate |
| Cost effectiveness | Modeled savings, verified savings, savings-estimation error, net savings after applicable fees |
| Recommendation quality | Acceptance/application rate, dismissal reasons, expired/irrelevant rate, eligible-candidate rate |
| System reliability | Runtime, failures, reproducibility, stale-input rejection rate |

## Important implementation notes

1. **Do not use a forecasting model to bypass hard constraints.** Forecasts inform the optimizer; they do not replace eligibility and compatibility checks.
2. **Treat P99 and peak separately.** P99 is less sensitive to one extreme sample; maximum can expose rare but important bursts. Neither alone guarantees safety.
3. **A capacity-ratio projection is an approximation.** CPU performance per core, memory pressure, workload concurrency and latency can invalidate a simple linear estimate.
4. **Use `Decimal` or equivalent exact decimal arithmetic for money.** Keep currency, billing period, units, price source and effective date explicit.
5. **Do not begin with reinforcement learning.** It needs a reliable reward signal, safe exploration and validated outcome data. Deterministic optimization and replay are more appropriate for the first version.
6. **Do not claim verified savings from modeled prices alone.** If actual billing data is unavailable, label results as modeled or estimated.
7. **Keep OptScale-inspired concepts distinct from verified OptScale implementation details.** This is a recommended CloudPilot design, not a claim that OptScale uses every listed algorithm.

## Recommended starting stack

- **Validation:** Pydantic; Pandera if tabular-data validation becomes substantial.
- **Statistics:** pandas/NumPy or an equivalent time-series processing layer.
- **Forecasting:** seasonal-naive and Ridge baselines first; LightGBM quantile regression only after backtesting supports it.
- **Optimization:** Python deterministic enumeration and explicit constraint checks.
- **Persistence:** the project's existing database, with versioned catalog, price snapshots and recommendation history.
- **Testing:** pytest, property-based tests where useful, deterministic historical replay and regression fixtures.

The initial goal is not to maximize the number of models. It is to produce recommendations that are **safe, compatible, cost-correct, explainable, reproducible and verifiable**.
