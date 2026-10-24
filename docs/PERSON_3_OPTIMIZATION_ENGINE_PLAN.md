# Person 3 — Optimization Recommendation Engine

Detailed implementation plan for the CloudPilot backend, candidate selection, cost planning, and policy gates.

Status: proposed implementation, not completed functionality. Assignment source: `../5people.md`, Person 3. Read alongside `PERSON_2_FORECASTING_AND_REPLAY_PLAN.md`.

For the repository-grounded build sequence, concrete contracts, full action/alert coverage and milestone exit gates, use [ENGINE_IMPLEMENTATION_ROADMAP.md](ENGINE_IMPLEMENTATION_ROADMAP.md). Its one-day milestone sequence supersedes the older hourly schedule in the team assignment.

## 1. Outcome and ownership

Build the authoritative service that answers: **Which exact action should the engineer consider, why does it satisfy the implemented checks, and what would the modeled bill become?**

Own FastAPI wiring, `backend/app/api/`, `backend/app/engine/`, recommendation/change schemas, SQLite metadata, cost calculations, final candidate selection, policy gates, decisions and authorization. Person 1 supplies data/catalogs; Person 2 supplies demand and replay evidence; Person 4 consumes APIs; Person 5 owns agent/execution adapters and measured workload benchmarks.

The UI, MCP agent and export path call the same services. The LLM never decides plan compatibility, recalculates authoritative savings, or bypasses a failed gate.

## 2. Scope decisions

Use `5people.md` for ownership and handoff sequencing. Preserve the local-first scope of `PRODUCT_DEFINITION.md`: deterministic recommendations, illustrative prices, persistent cost-plan decisions, and no required cloud credentials. ML, provider execution, GitOps and cloud emulation remain optional integrations.

Start with exact VM rightsizing and explicit no-action/insufficient-data outcomes. Add schedules, idle investigation, orphan review, plan composition and alerts after the first resource-to-recommendation flow works. Do not implement an unconstrained portfolio solver for the initial demo: independently enumerate resource plans, then enforce action conflicts and shared dependencies.

## 3. Architecture and module layout

```text
backend/app/
  main.py
  api/                   # Validation, serialization, shared error responses
  models/                # Agreed resource/recommendation/evidence contracts
  engine/
    policy.py            # Versioned rules and thresholds
    candidates.py        # Compatibility filters and capacity checks
    optimizer.py         # Orchestration and deterministic selection
    costs.py             # Decimal arithmetic and charge behavior
    schedules.py         # Calendar/timezone expansion and activity checks
    actions.py           # Resize, schedule, idle, orphan eligibility
    evidence.py          # Immutable evidence packet and version binding
    lifecycle.py         # Plan decisions and separate change approvals
    plan.py              # Compose actions and reconcile portfolio totals
  repositories/          # SQLite transaction/retrieval boundary
```

Keep business rules out of HTTP handlers. Add repositories against Person 1's final data interfaces; do not build a second generator or pricing catalog.

## 4. Engine flow

```text
Inventory + catalog + telemetry
  -> normalize and validate data/configuration
  -> obtain Person 2 demand/quality evidence
  -> enumerate compatible candidate plans
  -> run per-candidate capacity and policy checks
  -> attach historical replay and scenario evidence
  -> calculate each candidate's modeled cost
  -> select cheapest eligible outcome with deterministic tie-breaks
  -> persist recommendation + all candidate explanations
  -> engineer accepts/rejects plan item
  -> recompute composed plan and export
```

Core service: `optimize_resource(resource_id, as_of, policy_version) -> RecommendationResult`. Freeze the data cutoff and versions at entry so one run cannot mix catalog or telemetry revisions.

## 5. Shared data and evidence contracts

Agree IDs, UTC half-open observation windows, units and revisions during milestone M0. Source schemas belong to Person 1. Recommendation/change schemas belong to you. Forecast/replay results belong to Person 2 using the contract in their plan.

A recommendation stores:

| Group | Required values |
| --- | --- |
| Identity | ID, revision, resource ID/configuration revision, generated time |
| Outcome | Action, outcome, current plan, exact target plan/configuration |
| Demand | Window, p95/p99/max, forecast method/version, quality |
| Checks | Rule ID, passed/failed/unknown, actual value, threshold, unit, reason |
| Alternatives | Considered plans, eligibility, rejection reasons and modeled cost |
| Economics | Currency, period, charge breakdown, before/after, saving, one-time cost |
| Provenance | Dataset/catalog/price/policy/feature/model versions, evidence references |
| Review | Decision state, decision time, actor, prerequisites and risk rationale |

Use explicit outcomes: `recommendation`, `no_action`, `blocked`, `insufficient_data`, `unsupported`. Keep infrastructure/API failures distinct from a valid no-action result. Missing forecast data must not be caught as an empty successful recommendation.

## 6. Policy configuration

Own one versioned policy used by candidate checks, replay, schedules and exports. Starting values below are proposed demo defaults requiring team agreement, not production safety claims:

| Rule | Proposed value/behavior |
| --- | --- |
| CPU sizing limit | Demand ≤ 80% of candidate vCPU |
| Memory sizing limit | Demand ≤ 80% of candidate RAM |
| Disk occupancy | Used plus declared growth ≤ 80% of capacity |
| Telemetry | Person 2's agreed coverage/freshness/history checks |
| Production schedules | Block routine stop/start recommendations |
| Disk shrinking | Unsupported |
| Unknown required capability | Block eligible resize selection; expose unknown reason |
| Savings threshold | Positive modeled recurring savings for a downsize; configurable minimum |
| Evidence validity | Configuration/version match plus configurable maximum age |

Use one inclusive boundary definition consistently: demand exactly at the configured limit passes that numerical check. Other checks may still block. Store threshold version and values in evidence. Avoid a second hidden headroom multiplier in replay.

## 7. Candidate enumeration and selection

1. Fetch the current resource, configuration history, compatible regional catalog and price snapshot.
2. If required data quality fails, return `insufficient_data` with missing fields and remediation. Preserve investigation findings without sizing claims.
3. Convert historical usage to absolute demand using the configuration at each timestamp. Reject unsupported CPU semantics or unresolved configuration changes.
4. Build candidates only from real entries in the supplied catalog. Include current plan as the comparison/control candidate.
5. Filter region, resource type, architecture/family, storage mode, OS/licensing and declared resize compatibility. Unknown required compatibility is not passed.
6. For each candidate evaluate every gate, retain results, calculate costs and attach Person 2's replay/scenarios.
7. Select the least-cost candidate passing all required checks. Tie-break by smallest configuration change, then stable plan ID. Keep objective and tie-breaks versioned.
8. If current capacity is adequate and no cheaper eligible candidate exists, return `no_action`. If alternatives are blocked or unknown, explain them. Do not show a blocked cheaper candidate as the chosen recommendation.
9. If current capacity is under pressure, evaluate eligible upsizes even when cost increases. If none passes, return blocked/capacity-pressure evidence rather than inventing a larger SKU.

First implementation minimizes modeled recurring cost subject to gates. Keep one-time migration costs separately visible; optional payback/tie-break logic must be explicitly configured. Do not introduce an uncalibrated scalar risk penalty that makes hard safety failures tradable for savings.

## 8. Capacity rules

For each CPU/memory dimension:

```text
required_demand = max(historical_p99, observed_peak, forecast_demand_bound)
candidate_passes = required_demand <= candidate_capacity * policy_limit
```

If a forecast has no validated bound, use its labeled point estimate alongside historical evidence, disclose missing uncertainty, and follow the agreed forecast-required policy. Core deterministic mode can operate without learned forecasts; missing required telemetry cannot be substituted with a model.

Observed peaks are deliberately conservative for the initial build. Any outlier exclusion requires an explicit, auditable data-quality rule; never remove peaks because they reduce savings. Mark observed CPU saturation as unknown latent demand, preventing a confident downsize.

Check disk occupancy/growth, retained volume compatibility, IOPS and network independently. Do not infer disk IOPS from throughput, or convert a provider's unspecified network quality into Mbps. If the current VM has 8 vCPU and a peak of 3.2 used cores, a two-core plan fails physical capacity; four cores meets an 80% CPU limit exactly. It remains eligible only if memory, storage, compatibility, replay and all other required gates pass.

Historical and stress replay must pass the shared configured criteria. A zero allowed breach threshold is a reasonable initial conservative policy. Report breach frequency and denominator; this is not outage probability. Docker latency results apply only to the tested workload/configuration and cannot prove synthetic VM SLO compliance.

## 9. Action-specific rules

| Action | Eligibility and output |
| --- | --- |
| Downsize/upsize | Exact compatible target plan, projected demand/headroom, all gate results |
| Schedule | Non-production; full proposed off-hour telemetry; recurring/batch activity checked; explicit timezone and calendar |
| Idle stop/delete proposal | Sustained CPU, memory, I/O and network inactivity with adequate coverage; confirmed ownership/dependency review; delete additionally requires backup/deletion disposition; unresolved evidence produces investigation findings |
| Volume cleanup/IP release proposal | Attachment/assignment history, age, ownership and dependency evidence; volume deletion requires backup/deletion review; unresolved prerequisites produce review findings |
| No action/defer | Explain why no eligible beneficial action is available or what evidence is missing |

For an idle resource, low CPU alone is insufficient. A dormant batch job can still be essential. Missing ownership, backup knowledge, or dependencies blocks deletion readiness. A review-only orphan finding can be displayed, but exclude its savings from executable/accepted savings until the required review is resolved. Show conditional potential savings separately.

Scheduling eligibility examines activity in the actual proposed off-hours, including weekend and batch windows. Display conflicting activity instead of quietly assuming shutdown is safe. Build timezone-aware schedules in Asia/Kolkata, then convert running intervals to UTC for billing. Do not use naive timestamp arithmetic.

## 10. Cost engine and plan composition

Use `Decimal` or integer minor currency units. Keep internal precision; round at defined presentation/export boundaries. Only add compatible currencies. Attach catalog version, effective date, billing behavior, currency and tax/discount assumptions to every result.

For the illustrative hourly catalog:

```text
before = current_compute_rate * current_billable_hours + current_other_charges
after  = target_compute_rate * scheduled_billable_hours + retained_other_charges
recurring_saving = before - after
```

Calculate hours from a specified UTC calendar month, expanding schedules in Asia/Kolkata. Account for partial-hour/minimum-charge behavior declared by the catalog. Stopped compute can retain storage/IP/backup charges. Unknown billing semantics block numeric savings claims for that action. Prices are illustrative until actually verified; do not label these Utho savings.

Illustrative arithmetic only: for a 720-hour period, current compute ₹10/hour, candidate ₹6/hour and retained storage/IP ₹300, before is ₹7,500 and resize-only after is ₹4,620. If a schedule keeps 200 hours, combined after is ₹1,500 and combined saving is ₹6,000. Never add standalone resize saving ₹2,880 to standalone schedule saving ₹5,200: they overlap. These rates are fixtures, not provider quotes.

Plan composition rules:

- Recompute each resource's final configuration and schedule once.
- Resize plus schedule may compose; stop/delete conflicts with resize/schedule.
- Count a volume/IP by its billing identity once, even when linked from a VM.
- Treat shared dependency charges explicitly; removing a VM does not automatically remove a shared volume.
- Potential and accepted plan totals use a single compatible action set, not the sum of every recommendation card.
- Reject conflicting selections with structured reasons; do not silently discard user choices.
- Display upsizes as negative savings/cost increases and one-time costs separately.

Persist the billing period and versions with plan exports. Do not compare an old baseline against a new catalog without stating/recomputing the baseline.

## 11. APIs and shared services

| Endpoint | Backend service responsibility |
| --- | --- |
| `GET /api/health` | Local service readiness |
| `GET /api/summary` | Consistent filtered cost/opportunity aggregates |
| `GET /api/resources` and detail/metrics | Paginated inventory and peak-preserving chart data |
| `GET /api/plans` | Catalog/capability/version view |
| `GET /api/recommendations` and detail | Outcomes, candidates, evidence and decisions |
| `PATCH /api/recommendations/{id}` | Persist accept/reject/reset with revision checks |
| `POST /api/simulate` | Validate supplied candidate/schedule, then rerun checks and economics |
| `POST /api/verify` | Refresh available evidence; state modeled/measured/unknown explicitly |
| `GET /api/ml/benchmarks` | Serialize Person 2's measured method comparison |
| Plan read/update/export endpoints | Agree paths with Person 4; compose costs and persist selections |
| `GET /api/alerts` | Rule-triggered capacity, usage and budget findings |
| Change proposal/status endpoints | Optional separate lifecycle; never implicit cloud apply |

Publish schemas and fixtures first. Use consistent errors with code, message, details and request ID. Missing resource is 404, invalid input 422, stale revision/conflicting action 409. A valid insufficient-data analysis returns a typed result, not an HTTP server error. Use pagination and aggregated charts instead of sending the entire metric estate to the frontend.

`simulate` must use authoritative backend plan IDs and capabilities; ignore/reject browser-supplied prices or invented capacities. Return recalculated checks and costs without changing acceptance or approval state.

## 12. Persistence, evidence and lifecycle

Proposed SQLite records: recommendations/revisions, immutable evidence packets, candidate evaluations, decisions, plans/plan items, alerts, change proposals, approvals and audit events. Store snapshot references or hashes sufficient to reproduce decisions. Use transactions for decision plus audit and plan recomputation; enforce uniqueness/idempotency where actions can be retried.

Keep two independent state machines:

1. **Plan decision:** pending → accepted/rejected; reset returns to pending. Accepted means included in a modeled cost plan.
2. **Change workflow, when integrated:** proposed → approved → dry-run/prepared → applied → monitored, with blocked/failed/rejected/rolled-back outcomes and explicit simulated/live mode.

Approval binds exact resource, action, current configuration revision, target configuration, schedule, evidence versions, scope, actor and expiry. Material changes invalidate approval. Person 5 rechecks these conditions before an authorized execution adapter acts. Backend service checks apply equally to REST and MCP callers.

Do not mark `verified` merely because a simulator ran. Record separate fields for policy checks, historical replay, stress scenarios, measured benchmark and post-change verification. The local Docker lab has its own identity and explicit approval; accepting a synthetic cost plan does not authorize it.

## 13. Evidence and explanation output

Return a structured explanation that Person 4 and the agent can render without inventing facts:

- What changed: current plan → exact target and action.
- Why: absolute demand, retained peaks, projected headroom and alternatives.
- Economics: before/after charge rows, period, currency and assumptions.
- Validation: passed, failed and unknown checks; modeled versus measured results.
- Limits: missing capabilities, CPU-scaling approximation, forecast uncertainty and price provenance.
- Next step: review prerequisites, decision state, approval requirements and rollback information where supplied.

Use heuristic risk tiers only with transparent rules. A low-risk label must not hide unknown required constraints, and no risk score represents an outage probability.

## 14. Implementation milestones and handoffs

The confirmed product scope is one day. Use [the implementation roadmap](ENGINE_IMPLEMENTATION_ROADMAP.md) for detailed dependencies and completion gates; do not treat the historical 42-hour assignment as the available delivery window.

| Milestone | Implement | Evidence of completion |
| --- | --- | --- |
| M0 | Shared source/evidence contracts, policy, usable telemetry/catalog fixtures | Persons 1–5 can consume agreed contracts |
| M1 | Shared analytics, candidate enumeration, replay, cost and selection | Complete single-resource candidate matrix |
| M2 | Persistence, decisions, cost plan and export | Resource → evidence → accept → export survives restart |
| M3 | Schedules, idle/orphan proposals, conflicts and composed economics | All action types and hand-calculated combined bills |
| M4 | Estate analysis, filtered aggregates and four alert detectors | Complete, reconciled totals and explained alerts |
| M5 | Simulation/verification adapters and remaining integrations | Shared rules through UI, REST and enabled MCP |
| M6 | Acceptance, clean setup, assumptions and demo fixes | Reproducible core journey with recorded evidence |

Reserve the final quarter for acceptance and integration. Learned methods and cloud/provider integrations do not block the core flow. Missing mandatory actions or alerts remain incomplete core work, rather than being silently deferred as optional features.

## 15. Behavioral acceptance matrix

| Fixture/test | Required result |
| --- | --- |
| Steady-low workload | Cheapest eligible lower-cost plan selected |
| Eight-core API with short peaks | Unsafe two-core option rejected; four-core evaluated independently |
| Memory-bound VM | CPU-light downsize blocked by RAM requirement |
| Missing/stale telemetry | Insufficient-data outcome; no sizing recommendation |
| Saturated CPU | No confident downsize based on capped observed usage |
| Wrong region/family or missing capability | Failed/unknown gate; candidate cannot become eligible |
| Active nightly batch | Off-hours schedule blocked for overlapping window |
| Production schedule | Policy block with explicit reason |
| Unknown orphan owner | Ownership-review finding; deletion not ready |
| Resize plus schedule | Recomputed final bill; no additive savings double count |
| Shared volume/IP | Charged once; retained charge not silently deleted |
| Different calendar month | Actual interval and schedule hours used |
| Required upsize | Cost increase displayed correctly |
| Accept then restart | Decision and accepted-plan totals persist |
| Revision/evidence changed | Stale update/approval rejected |
| Forged browser price/capacity | Authoritative catalog used; invalid inputs rejected |
| Repeated proposal request | No duplicate operation from same idempotency key |
| REST versus MCP | Identical service-level eligibility and authorization |

Use small hand-calculated fixtures for economics and boundary conditions. Integration tests should exercise real shared services and persistence rather than duplicate rules in mocks. Run the backend test suite and one resource-to-export smoke path before handoff.

## 16. Definition of done

- A clean local run produces exact, explainable recommendations without credentials or trained models.
- All considered candidates retain passed/failed/unknown checks and authoritative costs.
- Peaks, memory pressure, bad data, incompatibility and prohibited schedules block affected proposals.
- Accepted plans persist, resolve action conflicts and reconcile charges without double counting.
- Evidence records are reproducible and truthful about modeled, measured and unknown results.
- Plan acceptance and infrastructure approval remain separate and version bound.
- Frontend and MCP consume the same backend rules; exports include assumptions and provenance.

First change: M0 contracts, policy and fixtures. Then complete single-resource evaluation, including historical replay, before selecting a recommendation. Follow with the persisted plan journey, all action types, estate/alert coverage and integration. Optional change adapters follow the core gates.
