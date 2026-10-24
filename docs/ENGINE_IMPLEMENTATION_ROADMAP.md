# CloudPilot implementation plan

Reference: [Algorithms and models](CloudPilot_Algorithms_and_Models.md). This plan
uses the delivered `test-data/` files and supersedes the old fixture/count/billing
assumptions in earlier planning documents. Progress is recorded below; planned
work is not a claim of completion.

## Delivery decisions

- Keep the existing FastAPI, Pydantic, SQLite, React and TypeScript stack. Start
  with deterministic statistics and candidate enumeration; learned models follow
  chronological evaluation, rather than blocking the application.
- Import the delivered 200 resources, 49 catalog entries, 432,000 VM observations,
  relationships, events, GPU telemetry and six months of synthetic billing.
  Derive counts and observation windows from the manifest, never workload names,
  profile labels, event descriptions or an expected-outcome oracle.
- Treat the telemetry as a historical snapshot. Its timestamps have no timezone;
  explicitly assume UTC for display/analysis and expose that assumption. Historical
  coverage is evaluated at the supplied cutoff; it does not establish live freshness.
- Use Decimal for money. The default comparison is the supplied quarterly price
  divided by three, a monthly equivalent rather than a monthly tariff. Preserve
  hourly and commitment prices separately. Stopping VMs saves zero under this
  snapshot. Unknown GPU/IP prices stay null and make estate totals incomplete.
- Fail closed on unverified region, resize, storage, IOPS/network capabilities and
  price provenance. CPU/RAM-feasible alternatives can appear as conditional review
  findings, with every blocker visible; they are never actionable recommendations.
- Separate a review queue from financially effective plan actions. Queuing a blocked
  finding does not reduce accepted-plan cost or authorize execution. Historical
  replay and modeled savings never become measured or verified savings.

## Milestones and exit gates

| Milestone | Implementation | Exit gate | Status |
| --- | --- | --- | --- |
| M0 — data foundation | Typed source adapters; strict CSV/reference validation; content hashes; atomic, cached SQLite import; manifest and quality report | Counts match delivered files; missing values stay missing; repeated startup reuses cache; no oracle/profile-label leakage | Complete |
| M1 — deterministic analysis | Coverage/freshness, quantiles, EWMA/MAD, peak demand, same-family candidate enumeration, Decimal costs, historical/stress replay and evidence | CPU/memory peaks reject undersized candidates; unknown compatibility blocks readiness; every candidate explains its result | Complete |
| M2 — review and cost plan | Versioned recommendations; persistent accept/reject/reset; audit; recomputed costs; review-only queue; JSON/CSV export; catalog-based simulation | Refresh/restart preserves decisions; stale revisions fail; review findings never inflate savings; charges counted once | Complete |
| M3 — connected application | Overview, combined inventory filters, resource telemetry, candidate evidence, recommendation review, plan/export and explained alerts | Browser journey uses backend data; empty/loading/error states; responsive layout; frontend production build | Complete |
| M4 — behavioral verification | Small, independent safety/economic fixtures plus delivered-data integration tests; setup/assumptions documentation | Backend tests and frontend build pass; inventory → evidence → review exercised in browser; export covered by integration tests | Complete |
| M5 — action/scenario coverage | Editable Asia/Kolkata schedules and activity replay, reviewed deletion prerequisites, budget configuration/alerts, fuller bottleneck/GPU analysis | No cash savings for stop-only schedules; batch activity blocks shutdown; unknown prices never become zero | Planned |
| M6 — optional demand models | Seasonal-naive baseline; chronological train/validation/test splits; Ridge only if evaluation justifies it | MAE/RMSE and baseline comparisons published; models cannot bypass hard constraints | Planned |
| M7 — dedicated local execution lab | Allowlisted Docker workload, repeatable baseline/load test, exact-change approval, measured result and verified restore | Real availability and measurements; audit; failed restore remains visible | Planned |

The first implementation increment targets M0–M4. M5–M7 remain explicit follow-up
work. No provider mutation, cloud credentials, paid API, LLM or Docker daemon is
required for the core application.

## Module boundaries

- `adapters/dataset.py`: validate and normalize source files, provenance and IDs.
- `repositories/estate.py`: indexed telemetry, cached analytics, decisions/audit.
- `engine/policy.py`, `statistics.py`, `costs.py`, `optimizer.py`: shared pure rules.
- `engine/service.py`: filtered summaries, recommendations, simulation and plans.
- `api/routes.py`: typed HTTP contracts and errors; no independent business rules.
- `frontend/src/`: API-driven views, evidence and review actions.

## API contract

Read paths: `/api/health`, `/api/dataset`, `/api/summary`, `/api/resources`,
`/api/resources/{id}`, `/api/resources/{id}/metrics`, `/api/plans`,
`/api/recommendations`, `/api/recommendations/{id}`, `/api/optimization-plan`,
`/api/optimization-plan/export?format=json|csv`, `/api/alerts`, `/api/audit`.
Writes: `PATCH /api/recommendations/{id}` (snapshot version + decision revision),
`POST /api/simulate` (catalog ID and demand multiplier, never client prices).
Accept means add to the local plan/review queue, never apply infrastructure changes.

## Required regression evidence

1. Short CPU peaks and memory pressure reject a cheaper, undersized target.
2. Missing/invalid observations reduce coverage; duplicate/off-grid rows fail import.
3. Unknown prices/capabilities stay unknown; unverified snapshots are not actionable.
4. Current, conditional, accepted and verified savings remain distinct.
5. Stop-only savings are zero; attached resources are not charged twice.
6. Decisions are transactional, audited, version-bound and survive restart.
7. Combined filters agree across inventory, overview and recommendations.
8. Exports carry assumptions, provenance, blockers and currency/billing basis.

## Deferred decisions

Region/capability verification needs authoritative provider data. A configurable
budget needs an actual user-supplied value; no budget-overrun alert is fabricated.
The manifest mentions oracle/label files that are absent; they are not required
and will never be optimizer inputs. Historical synthetic billing cannot verify
post-change savings. See `docs/assumptions.md` for the implemented policy values.
