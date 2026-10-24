# First increment acceptance

Date: 24 October 2026. Scope: roadmap M0–M4, not the complete competition release.

| Check | Result / evidence |
| --- | --- |
| Delivered source import | Passed: 200 resources, 49 plans, 432,000 VM rows, 28,800 GPU rows, 1,020 billing rows |
| Missing/duplicate source data | Passed: 2,880 explicit missing observations; ten identical source events deduplicated/reported; duplicate telemetry aborts/rolls back import |
| Peak and memory safety | Passed: independent fixture retains a peak absent from p99, rejects an undersized target, evaluates headroom/stress separately and blocks memory pressure |
| Provider unknowns | Passed: unknown capabilities block eligibility; current snapshot yields zero execution-ready changes |
| Partial/Decimal costs | Passed: known baseline ₹8,72,691 monthly equivalent, 30 unpriced resources, stop-only savings zero |
| Persistence and reconciliation | Passed: queue/reset/restart, stale revision, audit, environment totals and review-only exclusion from accepted savings |
| Simulation/export | Passed: authoritative catalog, no decision mutation, forged prices rejected, JSON evidence and CSV provenance exported |
| Filter and telemetry APIs | Passed: combined filters reconcile; chart peaks retained; missing-data outcomes abstain; GPU observations exposed |
| Backend automated suite | Passed: 16 tests, including invalid/overflow input and scaled scenario evidence; existing Starlette/httpx deprecation warning only |
| Frontend production build | Passed: TypeScript and Vite, 31 modules; no new dependencies |
| Browser journey | Passed: overview → candidate evidence → queue → cost plan → reset; search for vm-002 → resource chart/absolute demand/dependencies; 3× demand scenario showed 2,863 historical and 2,879 stress breaches |

Browser evidence: [dashboard](assets/cloudpilot-dashboard.png) and
[queued review plan](assets/cloudpilot-review-plan.png).
Current and accepted known costs both remain ₹8,72,691 with an accepted blocked
finding; accepted savings remain ₹0. The browser test decision was reset afterward.
The dashboard shows 87 investigation findings, 50 descriptive alerts, five
insufficient-data VMs and ₹34,080 in conditional opportunities. These figures do
not claim verified savings or production readiness.

The covered assertions are in `backend/tests/test_engine.py` and `test_api.py`.
A normal telemetry control and both capacity/quality failure cases are exercised.
The alarm detector is descriptive; no production false-positive/SLO claim is made.

Remaining work: editable schedule analysis, reviewed deletion prerequisites,
configured budget alerts, evaluated demand forecasting, dedicated measured Docker
approval/apply/restore lab, and optional MCP/GitOps/provider adapters. None is marked
passed. This increment does not satisfy the full U01–U12 competition gate.
