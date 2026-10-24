# Engine implementation roadmap

Date: 24 October 2026. Status: implementation plan; engine functionality is not yet built.

This is the execution sequence for the full recommendation and cost-planning engine. Read it with [the engine design](PERSON_3_OPTIMIZATION_ENGINE_PLAN.md), [the analytics design](PERSON_2_FORECASTING_AND_REPLAY_PLAN.md), and [the product scope](PRODUCT_DEFINITION.md). The milestone gates here replace the older 42-hour engine schedule. The confirmed delivery constraint is one day with five people; do not promise completion from that older schedule.

## 1. What exists and what we will deliver

Verified repository starting point:

- FastAPI wiring, configuration, request IDs, error responses and read-only inventory/catalog endpoints exist.
- SQLite connection setup exists; there are no domain tables, migrations, recommendations or saved decisions.
- `Resource`, `ProviderPlan` and `MetricSample` exist in `backend/app/models/contracts.py`.
- `MetricSample` already uses absolute CPU cores and GiB. No percentage conversion belongs in candidate evaluation.
- The shared fixture has one VM and its current plan, with no telemetry or alternative plans. It cannot support a valid resize recommendation yet.
- `engine/`, `ml/` and `repositories/` contain ownership placeholders. The frontend displays starter inventory only.

The full core deliverable covers exact resize recommendations, schedules, idle stop/delete proposals, volume/IP cleanup proposals, explained alternatives, persistent plan decisions, correctly composed costs, exports, and four alert families. A blocked or insufficient-data outcome is part of the product.

Keep the engine deterministic and local. Learned forecasts, an unconstrained portfolio solver, public-cloud apply, and GitOps are later integrations. The required local Docker experiment is a separate Person 5 workflow; cost-plan acceptance never starts it.
\
Use 120 VMs and 345,600 timestamped rows as the team release target from `5people.md`. Keep the timestamp grid and represent unavailable metric values explicitly. Engine loops and coverage denominators read the delivered dataset manifest; do not hardcode estate size.

## 2. How the supplied architecture maps to implementation

Reference: [the architecture diagram supplied for review](assets/engine-architecture-reference.png). Treat its product/provider labels as design inputs, not evidence of implemented integrations.

The supplied diagram has the right responsibilities. Refine its ordering so final selection happens only after every required candidate evaluation has finished:

```text
Freeze inventory, catalog, telemetry, billing and policy snapshots
  -> validate input identity, units and action-level eligibility
  -> shared analytics: quality, p50/p95/p99, peaks, trends, optional forecast
  -> enumerate catalog candidates and compatible action alternatives
  -> evaluate EACH candidate:
       compatibility + capacity + policy checks
       historical replay + required scenario checks
       authoritative bill and prerequisites
  -> select the least-cost feasible candidate with deterministic tie-breaks
  -> persist alternatives, evidence and recommendation
  -> accept/reject/reset within a versioned cost plan
  -> compose the final resource states, reconcile charges and export
```

Five clarifications to the diagram:

1. The early gate checks request permissions, exclusions, supported actions and input availability. Candidate-specific capacity and compatibility checks happen after candidates exist. A missing resize input need not prevent an independently supported orphan finding.
2. Cost, safety and replay are evaluators used by the optimizer. A candidate is not selected first and validated afterward. Required replay failures or unknown checks exclude it from selection.
3. The shared analytics layer is owned by Person 2. Statistics and historical replay work before any trained forecast exists. Model errors never become zero demand.
4. The catalog adapter supports illustrative local data now and verified provider data later. The diagram's “actual Utho catalog” is a future data source, not a current capability.
5. Lifecycle feedback records decisions, modeled changes and measured lab outcomes separately. Realized savings require actual comparable billing evidence; automatic retraining is outside the core build.

## 3. Boundaries and module ownership

| Area | Proposed implementation | Owner / boundary |
| --- | --- | --- |
| Source snapshots | `adapters/` and source repositories | Person 1: inventory, configuration history, raw metrics, manifest, catalog, charges and billing history |
| Demand evidence | `ml/quality.py`, `features.py`, `baselines.py`, `replay.py`, `scenarios.py` | Person 2: one shared implementation of quality, statistics and replay |
| Engine contracts | `models/optimization.py`, `cost_plans.py`, `alerts.py` | Person 3; extend source contracts with Person 1 |
| Frozen context | `engine/context.py` | Person 3: cutoff, period, snapshot identities, policy and method versions |
| Policy | `engine/policy.py` | Person 3: one versioned configuration consumed by analytics and engine |
| Candidate evaluation | `engine/candidates.py`, `evaluator.py` | Person 3: compatibility, policy gates, demand/capacity comparison, evaluator orchestration |
| Selection | `engine/optimizer.py` | Person 3: deterministic constrained enumeration |
| Billing | `engine/costs.py` | Person 3: Decimal charge calculation shared by recommendations and plans |
| Other actions | `engine/actions.py`, `schedules.py` | Person 3: eligibility, prerequisites and final-state transforms |
| Plan composition | `engine/plan.py`, `lifecycle.py` | Person 3: decisions, conflicts, revisions and recomputation |
| Alerts | `engine/alerts.py` | Person 3: detectors using shared analytics and billing evidence |
| Persistence | `repositories/` and ordered SQL migrations | Person 3: transactions, evidence snapshots, decisions and audit |
| REST / frontend | `api/`, `frontend/src/lib/api.ts` | Persons 3/4: serialization, contracts and views |
| MCP / lab | `mcp/`, `execution/` | Person 5 calls the same services; measured lab has its own approval lifecycle |

These are proposed files. Add them with their milestone rather than creating empty abstractions up front. Keep the current monolith and SQLite. Do not introduce a task queue or solver dependency for the first version.

## 4. M0: freeze contracts and usable fixtures

Before algorithm work, deliver the following agreed contracts and JSON examples. Unknown fields are explicit, not omitted and assumed safe. Existing Pydantic models forbid extra fields, so source model extensions, fixtures and frontend consumers must change together.

| Contract | Minimum additions / semantics |
| --- | --- |
| Resource snapshot | Creation time, state, ownership confirmation, exclusions, dependencies, attachment/assignment state and revisions; explicit backup/deletion review for destructive proposals |
| Configuration history | Effective `[start, end)` intervals and capacities; CPU architecture/family, storage mode, OS/licensing and resize compatibility |
| Dataset manifest | Dataset revision, cutoff, interval, expected grid, provenance, fixture IDs and configuration-history references |
| Metric sample | Retain absolute units; null means unavailable. Preserve maximums when ingesting sub-interval data; never treat a 15-minute average as an unobserved instantaneous peak |
| Catalog snapshot | Plan/version identity, valid region, effective date, architecture/family, compatibility, storage semantics, numeric IOPS and network capabilities when known |
| Charge definition | Stable billing identity, resource association, currency, rate/unit, quantity, billing granularity, retained-on-stop behavior, tax/discount assumptions and price provenance |
| Billing history / budgets | Separate actual or synthetic period records; declared scopes, timestamps, currency and budget periods |
| Demand evidence | Resource/configuration/dataset identity, observation window, quality by dimension, statistics, saturation, method/version and forecast status |
| Candidate evaluation | Exact target, check results, modeled bill, replay result, scenario results, prerequisites and limitations |
| Recommendation | Stable ID/revision, run ID, action, outcome, current/target state, alternatives, economics, evidence, decision state and freshness |
| Cost plan | ID/revision, one run/context, explicit billing month, selected recommendation revisions, schedules, totals and completeness |

Source adapters normalize percentages once using the configuration at the observation timestamp. Reject unresolved configuration boundaries or unsupported metric semantics. Do not multiply an existing `cpu_used_cores` value by vCPU again.

Use the current environment enum: `production`, `staging`, `development`. Keep `/api/plans` for catalog SKUs; use `/api/cost-plans` for user optimization plans.

The engine entry points should have these responsibilities:

```python
optimize_resource(resource_id, context) -> ResourceAnalysis
evaluate_candidate(resource_id, proposed_state, context) -> CandidateEvaluation
compose_plan(plan_id, expected_revision) -> CostPlanProjection
decide_recommendation(plan_id, recommendation_id, decision,
                      expected_plan_revision, expected_recommendation_revision,
                      actor) -> CostPlanProjection
detect_alerts(scope, context) -> list[Alert]
```

`context` binds the observation cutoff/window, billing period, resource/configuration, dataset/catalog/price/policy revisions, analytics method and scenario definitions. Capture it once per run. `evaluate_candidate` is shared by optimizer and simulation; it never modifies decisions or applies infrastructure changes.

Create small hand-calculated fixtures for low demand, short peaks, memory pressure, required upsize, missing/stale data, saturation, wrong region, unknown capability, equal-price candidates, schedule/batch conflict, confirmed idle/orphans, unknown ownership, retained/shared charges and each alert family. Keep these separate from the full estate fixture.

Exit gate: source and engine contracts parse those fixtures; Persons 2/3 agree on the same units, windows and threshold semantics; Person 4 has response examples for every outcome. A mocked response remains labeled a contract fixture.

## 5. M1: one resource, complete candidate evaluation

### Data quality and policy defaults

Use policy `demo-v1` with documented starting values. These are demonstration choices and must be frozen before comparing savings.

| Check | Initial behavior |
| --- | --- |
| Observation window | Trailing 30 days before `as_of`, with at least 7 days of history required for baseline sizing |
| Expected samples | Derive from the declared observation grid, including missing leading/trailing intervals |
| Valid coverage | At least 95% for each required dimension over the requested window and each full UTC day; a resource with only 7 days does not pass a requested 30-day window |
| Freshness | Latest valid required observation within two declared intervals of `as_of` |
| Continuous gap | No required-dimension gap longer than 2 hours |
| CPU / memory | Required absolute demand at most 80% of candidate capacity; equality passes |
| Disk | Used capacity plus declared growth at most 80%; no disk shrinking |
| IOPS / network | Compare only matching demand/capacity semantics; unknown required limits block eligibility |
| Saturation | Observations at or above 99% of allocated CPU flag censored demand; prohibit a confident downsize |
| Replay | Zero policy-limit breaches allowed on required, evaluable dimensions |
| Price | Known compatible currency and charge behavior; unknown required charges prevent a complete savings claim |
| Downsize economics | Strictly positive recurring saving; retain current state on a zero-saving tie |
| Evidence age | At most 24 hours from the recorded analysis reference time, plus exact revision matching; display synthetic replay time separately from wall-clock generation time |

Data freshness uses the explicit analysis cutoff. Synthetic fixtures may use a frozen cutoff, labeled throughout the UI/export. Never present historical synthetic evidence as a current provider observation. At plan mutation, validate that the dataset/configuration/catalog/policy context is still the active context for that plan; future live adapters also check wall-clock freshness.

Person 2 supplies quality and features. Do not write an alternative feature implementation inside `engine/`. If that module is late, integrate through its agreed fixture interface and mark integration incomplete until actual telemetry passes through it.

### Candidate evaluation and selection

1. Resolve the current resource/configuration and current-plan baseline. Include the current state as a control; preserve its failed and unknown checks too.
2. Keep every regional catalog alternative in the explanation, including compatibility rejection reasons. Never invent a SKU.
3. Compute `required_demand = max(historical_p99, observed_peak, available_forecast_estimate)` for CPU and memory. Label the forecast estimate as a point or validated bound; deterministic mode omits an unavailable optional forecast and records that fact.
4. Compare demand with `capacity * policy_limit` using a defined numeric representation. Normalize decimal boundary values before comparison so the 3.2-core / 4-core / 80% fixture passes consistently.
5. Evaluate disk, IOPS, network and action-specific policy independently. Record `passed`, `failed`, `unknown`, or explicit `not_applicable` with reasons. Applicability is policy-defined; callers cannot mark inconvenient checks optional.
6. Replay the ordered historical samples against each candidate using the same thresholds. Count distinct breached timestamps, denominators and longest runs. Missing data stays unknown; do not count it as zero usage.
7. Evaluate required stress scenarios when configured, and calculate the authoritative candidate bill. Core historical replay is required. Interactive growth scenarios are opt-in previews until a versioned policy explicitly makes a scenario mandatory; report that distinction.
8. Only candidates with all applicable required checks passed are eligible. Select by recurring cost, then unchanged-current-state preference, then number of changed capacity fields, absolute vCPU difference, absolute memory difference, and stable plan ID. This ordered tuple is versioned; do not add GiB and cores into a scalar distance.
9. If current capacity is adequate and certified under the required checks, retain it when no cheaper eligible alternative exists. If capacity is pressured, choose an eligible remedy even if cost rises. Unknown latent demand cannot certify an upsize from capped telemetry alone.

Outcome precedence:

| Outcome | Meaning |
| --- | --- |
| `unsupported` | Resource/action semantics are not implemented |
| `insufficient_data` | Required observations, configuration identity or quality are inadequate |
| `recommendation` | An exact eligible beneficial change or capacity remedy is available |
| `no_action` | Current state passes required checks and no beneficial eligible alternative exists |
| `blocked` | Analysis is possible but required compatibility, policy, capability or pricing checks prevent a defensible choice |

Programming errors, adapter failures and unavailable databases remain operational errors. Do not translate them into `no_action` or `insufficient_data`.

First handoff example: an 8-vCPU/16-GiB VM with peaks of 3.2 cores and 5 GiB. A 2-vCPU candidate fails CPU; a 4-vCPU/8-GiB candidate meets CPU exactly and passes memory at 62.5%. It becomes recommended only if compatibility, storage, IOPS, network, replay and economics also pass. Preserve both rows in the response.

Exit gate: the candidate matrix is derived from real fixture telemetry through shared analytics, peak and memory failures are explained, unknown capabilities cannot pass, and repeated identical inputs yield identical evaluation content. Generated IDs/timestamps may differ; candidate order and selection must not.

## 6. M2: persistence, a decision and an export

Implement the first complete journey before expanding actions:

```text
analyze VM -> persist evidence -> inspect alternatives -> accept resize
  -> read updated cost plan -> restart API -> read same decision -> export
```

Use ordered SQL migrations with a schema version table. Start with analysis runs, immutable recommendation/evidence revisions, candidate evaluations, cost plans/items, decisions and audit events. Add alerts and change records in their own milestones. Store snapshot contents or immutable references plus hashes; a hash without retrievable inputs is insufficient for reproduction.

One optimization run has a frozen scope/context and an explicit status. Evaluate outside a long SQLite write transaction; publish completed results coherently. Do not mix incomplete runs into overview totals. Resource-level valid blocked outcomes are completed analyses; infrastructure exceptions mark a run failed. Store run duration and counts for diagnosis.

Decisions are `pending`, `accepted`, `rejected`; reset returns to pending. For the initial single-organization local app, record the configured demo engineer as the actor without claiming authentication or RBAC. Optional MCP access must use its configured caller permissions, while all entry points enforce the same domain gates.

Scope each decision to `(cost_plan_id, recommendation_id, recommendation_revision)`. Accepting a recommendation in one plan does not accept it in another. Recommendation evidence remains immutable; API decision fields are a view for the requested plan.

Decision updates must:

- Check both recommendation and plan revisions using compare-and-swap semantics.
- Revalidate active configuration/evidence, required gates and prerequisites at the service boundary.
- Update the decision, compose/validate the plan, increment its revision and write the audit event in one transaction.
- Roll back the whole mutation on a conflict. The API returns 409 with affected action/resource identities.
- Support retried mutations with an idempotency key; the same key/body returns the original result, and a different body with the same key conflicts.

A new analysis never silently transfers acceptance to a changed target or evidence revision. Mark old items stale and require explicit revalidation. Historical exports remain immutable. A current plan with stale items must report incomplete/needs-revalidation rather than silently presenting a new accepted total.

Export CSV and JSON from the same committed projection. Include period, plan/recommendation revisions, exact targets, charge rows, assumptions, evidence references, limitations, prerequisites and actor/time. No browser-side savings calculation.

Exit gate: accepting/rejecting/resetting changes totals correctly, stale writes fail, rejected mutations leave no partial audit/decision changes, and state survives a new app process.

## 7. M3: all actions and correct composed economics

### Action eligibility

| Action | Required evidence / behavior |
| --- | --- |
| `resize` | Exact target SKU; all candidate gates; direction may be down, up or mixed |
| `schedule_stop_start` | Non-production; explicit weekly calendar in Asia/Kolkata; evaluate the actual proposed off-hours including weekends and batch activity |
| `stop_idle` | Non-production core policy; sustained inactivity, confirmed owner/dependencies and a reviewed stop proposal; retain declared storage/IP/backup charges |
| `delete_idle` | Idle evidence plus explicit owner authorization evidence, resolved dependencies and backup/deletion disposition; export a proposal, never execute from acceptance |
| `cleanup_volume` | Confirmed detachment history/age, owner and backup/deletion review; valuable unattached data is not automatically disposable |
| `release_ip` | Confirmed assignment history/age, ownership and resolved DNS/dependency review; no assumed deletion of linked resources |

Initial idle defaults: at least 7 complete days within the quality-approved window; every valid observation stays below 2% allocated CPU, 10% allocated memory, 1 IOPS and 0.1 Mbps in each network direction. Apply coverage/gap checks to every required dimension. Schedule off-hours use the same activity limits, with coverage assessed per local weekday/off-hour group. Start with running Monday–Friday, 08:00–20:00 Asia/Kolkata, and stopped otherwise. Store timezone, weekdays and half-open local running intervals explicitly; edits create new evaluated evidence. Any conflicting activity blocks the proposed schedule. Thresholds are conservative demo heuristics, not proof that a workload is unnecessary.

For orphan proposals, require at least 7 days of continuously known detached/unassigned state. A current unattached flag with no history produces a review finding. Missing owner or dependency/backup review stays blocked; include confirmed fixtures so the product also demonstrates eligible cleanup proposals. Production stop/delete is blocked by the core routine policy; exception workflows are later work.

### One billing implementation

Use `Decimal` internally. Charge rows carry stable billing identity, rate/unit, quantity, currency, period and price version. Compute baseline and projected bills from resulting states under the same context:

```text
baseline = sum(charge(current state, baseline calendar))
projected = sum(charge(final selected state, final calendar))
recurring_saving = baseline - projected
```

The initial catalog declares hourly compute billing; expand schedules into a UTC calendar-month interval and apply the catalog's billing quantum/minimum rules. Running hours are not a fixed 720. Use half-open intervals, handle local dates crossing the UTC month boundary, and clip each interval once.

Include storage, IP, backup, egress and other charges only with declared billing behavior. A fixture can explicitly declare no such charge; missing pricing is unknown, not zero. Do not imply a usage spike changes fixed-plan compute cost.

Keep current, compatible potential-plan and accepted-plan projections separate. Round each displayed/exported charge row to two decimals using `ROUND_HALF_UP`, sum those same rounded rows for displayed aggregates, and derive displayed savings from displayed before/after totals. Retain unrounded values for selection and traceability. Do not combine currencies. Report completeness and unpriced-resource counts; an incomplete subtotal is not an estate total.

Composition rules:

- Apply resize plus schedule to one final VM state and bill it once.
- Stop/delete conflict with resize/schedule; stop and delete are mutually exclusive alternatives.
- A VM deletion does not imply deletion of its separately billed volumes/IPs. Explicit compatible cleanup proposals are separate actions.
- Deduplicate shared billing identities and preserve shared dependencies. A referenced charge is not a second charge.
- Reject multiple conflicting resize targets or schedules instead of silently choosing one.
- A prerequisite failure blocks inclusion in the accepted projection. Conditional review savings are shown separately.
- Calculate potential savings from one feasible action set: evaluate resize/schedule combinations, stop/delete alternatives and dependency constraints. For shared-resource conflicts, choose a deterministic feasible set and label it a heuristic, not a globally optimal portfolio.
- Apply orphan attribution from the source inventory; use an explicit unallocated bucket when environment/team is unknown. Environment buckets, including unallocated, must sum to the estate view.
- Keep one-time change cost and any future observed/realized saving separate from recurring modeled savings. A required upsize can have negative savings.

Arithmetic fixture: 720 hours, compute rates ₹10 and ₹6/hour, retained charges ₹300. Baseline ₹7,500; resize-only ₹4,620; schedule-only at 200 hours ₹2,300; combined resize/schedule ₹1,500. Combined saving is ₹6,000, not ₹2,880 + ₹5,200. These are illustrative rates and an explicit test period, not provider quotations or a default month length.

Exit gate: each action has both eligible and blocked examples, batch activity blocks off-hours shutdown, combined economics match hand calculations, and per-resource/environment/estate totals reconcile after decisions and restart.

## 8. M4: estate aggregation and four alert detectors

Scale the same evaluator to the source manifest. Fetch telemetry in batches and compute resource features once per frozen context, reusing them for candidate evaluation. Do not reload the estate or scan all telemetry for each SKU. Keep raw metrics server-side and return peak-preserving chart aggregates with explicit gaps.

Initial alert rules belong in the same versioned policy:

| Family | Proposed deterministic rule | Required output / missing-data behavior |
| --- | --- | --- |
| Usage spike | Latest hour CPU or memory peak exceeds 2× the preceding 7-day p95 and exceeds an absolute floor of 0.5 used cores or 1 used GiB | Observed value, baseline, ratio, floor and window. A zero baseline uses the absolute floor; insufficient history abstains |
| Cost increase | Latest complete billing month is at least 20% above the previous complete month | Same-currency charge breakdown and period lengths; explain actual modeled billing changes. Zero prior spend is a separate new-spend finding |
| Capacity pressure / trend | Latest hour p95 reaches 80% capacity, or a positive linear trend over 7 daily p95 values projects reaching 80% within 7 days | Actual/trend trigger, dimension, capacity, slope and assumptions; require all 7 quality-valid days for trend. Unknown numeric capabilities cannot produce a numeric utilization claim |
| Budget overrun | Month-to-date spend plus remaining-hours run-rate exceeds the scoped monthly budget | Spend cutoff, elapsed/remaining hours, projected total and budget; zero elapsed time, missing charges or mismatched periods yields unavailable |

Trend extrapolation is labeled a deterministic projection, not a validated long-range forecast. Detector evidence must identify synthetic billing records. Four positive fixtures and a normal control are required; optional ML never blocks these detectors.

Persist alerts with a deduplication key for rule, scope, evidence window and policy version; rerunning the same window does not flood duplicates. Store trigger evidence and resolved/current status. Summary filters and resource filters use the same region/environment/team semantics and analysis run.

Exit gate: all four families are derived from inputs, normal controls stay clear, unknown inputs remain explicit, combined filters reconcile, and full-estate run time/memory are measured and recorded without inventing a performance claim.

## 9. M5: API, frontend and integration contracts

Keep reads side-effect free. Start with an explicit synchronous analysis request for the bounded local estate; add background execution only if measured runtime requires it. Do not hold a SQLite write lock while running analytics. A failed request/run remains observable and retryable by idempotency key.

| Endpoint / family | Milestone / responsibility |
| --- | --- |
| Existing `GET /api/resources`, resource detail, `/api/plans`, `/api/health` | Preserve compatibility; add source fields with synchronized consumers |
| `POST /api/optimization-runs` | M1 single-resource scope; M4 estate scope. Accept `as_of`, observation window, billing month and policy ID; resolve snapshot versions server-side |
| `GET /api/optimization-runs/{id}` | M2 status, context, counts and failure details |
| `GET /api/recommendations` and `/{id}` | M2 stored outcomes, exact targets, candidates and evidence; pagination and run/scope filters |
| `POST /api/cost-plans`, `GET /api/cost-plans/{id}` | M2 create/read a plan bound to one context |
| `PATCH /api/recommendations/{id}` | M2 decision body includes plan ID, both expected revisions and idempotency key |
| `PATCH /api/cost-plans/{id}/schedule` | M3 edit a selected schedule; rerun eligibility and costs, increment revision and invalidate changed evidence |
| `GET /api/cost-plans/{id}/export?format=csv\|json` | M2/M3 consistent committed projection and evidence |
| `GET /api/summary`, `/api/resources/{id}/metrics` | M4 filtered aggregates, chart resolution and quality metadata |
| `GET /api/alerts` | M4 detector output with provenance |
| `POST /api/simulate` | M5 calls `evaluate_candidate`; target plan ID, schedule and allowed scenario parameters only; no decisions changed |
| `POST /api/verify` | M5 refresh modeled evidence with explicit check status; does not claim measured validation |
| MCP tools and local lab APIs | Person 5 uses the same domain services; separate lab identities/approval |

Reject browser-supplied prices/capacities and unsupported scenario parameters. Use existing structured errors: 404 missing resource, 422 invalid request, 409 stale/conflicting mutation. Valid blocked/insufficient-data analyses are typed successful responses; operational failures are errors. Update CORS methods/headers when write endpoints are introduced; current configuration allows only GET.

Risk labels use published rules, not an invented probability: blocked/unknown required checks cannot produce an eligible low-risk proposal; eligible downsizes may carry a documented heuristic tier, while upsizes, schedules and destructive proposals expose their specific operational consequences. Return unavailable confidence when no calibrated estimate exists. Explanations are generated from check/economic evidence before any optional LLM wording.

Change approvals, provider dry-runs and applied/monitored states are later adapters to the shared lifecycle. For the required lab, approval binds the exact allowlisted container, original/target limits, evidence, actor and expiry. A modeled plan decision cannot substitute for this approval. Person 5 owns real measurements and restore; Person 3 owns the service-level state validation used by those endpoints.

Exit gate: frontend completes resource → evidence → accept → plan → export; simulator and optimizer return matching evaluations for identical proposals; MCP, when enabled, cannot bypass domain gates; lab absence or failed restore stays visible.

## 10. M6: acceptance, handoff and delivery order

Use these milestone gates, not a claim that the engine fits the old 42-hour timetable. Percentages are a planning allocation of available engine work time; they are not measured effort estimates.

| Order | Allocation | Deliverable / dependency |
| --- | --- | --- |
| M0 | 10% | Source/evidence contracts, policy, fixture manifest; coordinate Persons 1/2/4/5 immediately |
| M1 | 15% | One real candidate matrix; depends on quality/features/replay and known catalog charges |
| M2 | 15% | Saved recommendation → decision → one-resource plan → export; frontend integrates here |
| M3 | 15% | Schedules, idle/orphan proposals, conflicts and combined costs |
| M4 | 15% | Estate run, filtered aggregates and four detectors |
| M5 | 5% | Remaining simulation/verification adapters and integration fixes; frontend/MCP/lab integration starts earlier |
| M6 | 25% | Freeze behavior, run acceptance, fix defects, verify clean setup, document and rehearse |

No milestone is complete because its allotted time expired. If time is insufficient, record missing mandatory coverage and redirect optional work to it; do not silently relabel required actions or alerts as stretch scope. Learned model experiments, provider integrations and portfolio solvers stay deferred until the core gates pass.

Required verification, written alongside the corresponding feature:

| Group | Behavioral checks |
| --- | --- |
| Identity / quality | Correct configuration per timestamp; no double conversion; missing memory; stale sample; duplicate/invalid timestamps; requested-window gaps; future observations beyond cutoff do not change an earlier analysis |
| Selection | Exact 80% boundary; short peak; memory bound; saturation; unsupported family; unknown required IOPS/network; deterministic ties; positive saving; valid capacity upsize; current control can fail |
| Billing / composition | Calendar lengths/leap February; Asia/Kolkata month boundary; billing quantum; retained/shared charges; resize + schedule; conflicting actions; unknown pricing; negative saving; rounding and currency; environment totals equal estate totals |
| Actions | Every action has an eligible fixture; unknown owner/dependencies/backup blocks deletion; active batch blocks schedule; production routine stop/schedule policy; no implicit volume/IP deletion |
| Persistence / API | Restart; accept/reject/reset; stale plan and recommendation revisions; repeat idempotency key; transaction rollback; stale regenerated evidence; export matches committed projection; forged price/capacity rejected |
| Alerts / integration | Four positives plus control; duplicate alert suppression; filter consistency; missing billing; simulation/evaluator parity; enabled MCP permission checks; lab approval and restore handled separately |

Use small independent hand calculations and behavioral integration tests. Avoid tests that merely restate implementation internals. Run `uv run --directory backend pytest` and `npm --prefix frontend run build` after implementation, plus the resource-to-export flow from a clean local database. Record actual outcomes and commands in `docs/acceptance.md`; these checks have not been run as part of this planning document.

Person 3 supplies pricing/policy/cost/alert assumptions to `docs/assumptions.md`; Person 1 supplies data provenance and Person 2 supplies analytics limitations. Person 5 assembles release evidence and the separate Docker experiment. The full product gate remains U01–U12 in `5people.md`; a completed backend milestone alone is not a complete competition submission.

First implementation change: M0 contracts, policy fixture and independently calculable cases. First working behavior: M1's single-resource candidate matrix. First reviewable product journey: M2's persisted decision and export. Expand only after that journey is reproducible.
