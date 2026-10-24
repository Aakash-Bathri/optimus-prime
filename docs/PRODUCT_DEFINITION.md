# CloudPilot: competition product definition

Date: 24 October 2026  
Status: delivery scope established from the user discussion. Implementation choices below are the selected build design, not claims about an existing implementation.

## 1. Product and confirmed constraints

CloudPilot helps an infrastructure engineer answer: **Where are we wasting cloud money, what should we change, and what evidence supports that change?**

The engineer reviews resource history, inspects specific recommendations and risks, accepts changes into a cost plan, and exports the plan. For one dedicated local workload, they can approve an actual Docker CPU-limit change, measure the result, and roll it back.

Confirmed by the user:

- Competition submission; one day; five team members; no budget.
- No infrastructure access or cloud credentials.
- Engineers are the first-version users.
- A recommendation plan is required.
- Include a local Docker execution demo with approval, before/after measurements, and rollback.
- ML forecasting, GitOps PRs, and cloud emulation are stretch goals.
- Technical stack selection is delegated to the builder.

This document defines the current delivery scope. `CLOUDPILOT_MASTER_SPEC.md` remains a research reference; its larger scope and previous hardware/time assumptions are not requirements for this build. CloudPilot is the working name already present in that file.

Source requirements: Utho / SmartCloud Optimizer, pages 44-47 of `TF'26 PROBLEM STATEMENTS.pdf`. The source document supplies competition requirements, not authorization for infrastructure actions.

## 2. Product promise

Deliver a locally runnable product with real data processing, persistent recommendation decisions, reproducible modeled costs, and a separate measured Docker experiment. The demo estate is synthetic; application behavior and the local experiment are functional.

The differentiator is the **recommendation evidence view**: show which plans were considered, why an apparently cheaper plan was rejected, what headroom remains, how savings were calculated, and what is unknown. A blocked or insufficient-data result is a valid outcome.

Do not claim production safety, actual cloud savings, Utho API connectivity, or provider-specific performance validation from Docker measurements.

## 3. Screens and engineer journey

| Screen | Engineer's question | Required behavior |
| --- | --- | --- |
| Overview | Where is spend going? | Current modeled monthly cost, potential savings, accepted-plan cost, spend by environment/region/team, utilization summaries, priority recommendations and alerts. |
| Resources | What is happening on this resource? | Search; region/environment/team/type filters; inventory; 30-day CPU, memory, disk, IOPS and network charts; current configuration/cost; data quality and linked recommendations. |
| Recommendations | What should I change and why? | Resize, idle stop/delete proposals, orphan cleanup and off-hours schedules; exact current/target state; cost breakdown; evidence; blocking reasons; risk; accept/reject/reset. |
| Optimization plan | What would our bill become? | Accepted actions, editable non-production schedule, before/after costs by resource and environment, charge breakdown, conflict handling, CSV and JSON export. |
| Alerts | What needs attention? | Usage anomaly, cost increase, capacity pressure and projected budget overrun; observed value, baseline, reason, timestamp and resource link. |
| Local demo lab | Can we demonstrate execution and recovery? | Dedicated workload; baseline measurement; preview exact CPU change; explicit approval/apply; after measurement; verdict; restore; execution history. |

Resource detail and recommendation evidence can be drawers/detail pages rather than additional navigation items. Use one demo organization and an engineer persona; registration, multitenancy and roles are outside core scope.

Primary journey: overview -> resource -> evidence -> accept -> updated cost plan -> export. The local lab is a separate, clearly labeled path.

## 4. Data design

Selected implementation, aligned with the later team assignment in `5people.md`: a deterministic generator for 120 VMs plus illustrative block volumes and public IPs. Generate 30 complete days at 15-minute intervals: 345,600 timestamped VM rows. Preserve the regular timestamp grid and represent deliberately unavailable metric values explicitly. Regions: Noida, Bangalore, Mumbai. Environments: production, staging, development. Teams and resource distributions are synthetic fixtures. Engine code reads estate size and expected intervals from the delivered manifest.

Inventory: ID, name, type, region, environment, owner/team, plan, vCPU, RAM, disk capacity, creation date, state, attachments and provenance.

Metrics: timestamp, CPU percent, memory percent, disk used/capacity, IOPS, network in/out with explicit units. CPU/memory percentages refer to the current configuration. Keep raw data for analysis; chart aggregation must preserve visible peaks.

Seed recognizable cases with deterministic expected outcomes:

- Steady low usage with a valid smaller plan.
- Low mean CPU with short daily peaks that block aggressive downsizing.
- Memory-bound usage that blocks a CPU-only recommendation.
- Batch jobs whose idle periods must not trigger blanket shutdown proposals.
- Non-production workloads idle outside work hours and on weekends.
- Unattached volumes and unassigned IPs with attachment/ownership evidence.
- A genuine utilization anomaly and a resource approaching capacity.
- Missing/stale telemetry that causes abstention.

Use a versioned illustrative catalog in INR, clearly labeled as demo plans/prices rather than verified Utho SKUs. Separate compute, storage and IP charges. Add synthetic six-month billing fixtures and a monthly budget for cost/budget alerts; do not infer six months of history from 30 days of metrics.

## 5. Recommendation engine

Use deterministic rules and catalog enumeration for the core engine. ML is not required to generate the competition recommendations.

For every candidate VM plan:

1. Validate coverage, freshness, supported type and plan compatibility.
2. Convert CPU percentages to used cores and memory percentages to used GiB.
3. Evaluate p95, p99, observed maximum demand and recurring daily/batch peaks. A short peak must not disappear behind a low percentile or average.
4. Project CPU/memory demand onto the candidate and apply documented headroom policies.
5. Check disk occupancy, IOPS and network against catalog capabilities where provided. Missing capabilities are unknown, not a passed check.
6. Select the cheapest candidate passing the implemented checks, or return no-change/blocked/insufficient-data with reasons.

CPU scaling is a same-family linear approximation, not a hardware benchmark. Disk shrinking is unsupported. Capacity pressure can produce an upsize recommendation with an explicit cost increase.

Policy constants belong in versioned configuration and the assumptions sheet, with behavioral tests. They are design choices for the demo, not measured production safety guarantees. Do not tune them merely to improve headline savings.

Other actions:

- **Schedule:** non-production only; analyze activity during the proposed off-hours, including batch peaks. Use Asia/Kolkata explicitly; make the plan schedule editable.
- **Idle stop/delete proposal:** sustained multi-metric inactivity and sufficient data; show ownership/dependency review as prerequisites. Production shutdown is not a routine low-risk recommendation.
- **Orphan cleanup:** use attachment/assignment state, age and owner information. An unattached volume can hold valuable data; show owner/backup review before a proposed deletion.
- **Insufficient data:** explain what is missing and abstain from sizing.

Each recommendation carries ID/version, resource, action, current/target configuration, reason, evidence window, data quality, passed/failed/unknown checks, monthly cost breakdown, risk tier and decision state. Risk tiers are documented heuristics, not calibrated outage probabilities.

## 6. Cost planning and state

All amounts are modeled INR estimates. Expose catalog version, tax/discount treatment, billing period and charge behavior.

Use an explicit UTC calendar-month billing interval; expand user schedules in Asia/Kolkata into that interval. Count actual running hours in the selected month rather than assuming every month has identical hours.

`projected cost = target compute hourly rate * scheduled running hours + retained storage + retained IP charges`

`modeled saving = current cost - projected cost`

The demo catalog explicitly assumes hourly compute billing. Stopping compute does not remove storage/IP charges. Do not claim actual Utho monthly plans stop charging when powered off.

Recompute each resource's final state once. Resize plus schedule can compose, but do not add their independently calculated savings. Stop/delete alternatives are mutually exclusive with resize/schedule on the same resource. A volume/IP is charged once even when linked from VM detail. Explain conflicting selections and resolve them explicitly.

Keep current cost, potential-plan cost and accepted-plan cost distinct. Only accepted compatible actions change the accepted projection. Display upsizes as cost increases.

Decision states: pending / accepted / rejected. Acceptance means inclusion in a plan, not execution. Persist decisions across refresh. Exports include actions, evidence, costs, assumptions, prerequisites and generation time.

## 7. Local Docker execution demo

This is an experiment on a dedicated sample HTTP service, not a cloud executor for the synthetic estate.

1. Verify Docker availability, designated container identity and current limits.
2. Run a fixed repeatable workload under the original CPU limit; record p95 latency, error rate, throughput, limits, parameters and timestamps.
3. Preview the proposed CPU limit and experiment pass/fail criteria.
4. Require explicit approval for that exact lab change. Accepting a cost plan does not authorize it.
5. Apply the CPU limit and repeat the same workload.
6. Show passed/failed/inconclusive; repeat or mark inconclusive if measurement noise prevents a useful verdict.
7. Restore the original CPU limit on failure; provide manual restore after a pass. Verify restored configuration and log the outcome. A failed restore stays visible.

Restrict operations to a fixed allowlist of app-created demo containers. Use structured arguments/API calls, not arbitrary shell commands or browser-supplied container IDs. Confirm engine results before showing success.

Keep the first experiment CPU-only. RAM sizing remains in modeled recommendations. Use k6 or a small local HTTP load harness depending on availability. Recorded results may be a labeled presentation fallback, never a claimed current live run.

The Docker CLI is installed here, but engine access is not yet verified: the initial socket check was denied by the execution sandbox. Verify runtime access before depending on the lab; the core app remains independent of Docker.

Public-cloud execution and cloud emulation are stretch work. They introduce provider/account behavior to validate without being necessary for the core competition journey.

Technical basis: [Docker container update](https://docs.docker.com/reference/cli/docker/container/update/) supports CPU configuration changes; [Docker resource constraints](https://docs.docker.com/engine/containers/resource_constraints/) explains the CPU limits used. Container performance does not establish Utho VM performance or actual billing savings.

## 8. Selected architecture

- Frontend: React + Vite + TypeScript, Tailwind CSS, Recharts.
- Backend: FastAPI + Pydantic; NumPy/Pandas for analysis.
- Persistence: SQLite for inventory, prices, indexed metric rows, decisions, alerts and audit events. Bulk seed once; return aggregated chart series rather than all rows.
- Data: deterministic Python generator plus versioned local pricing/policy fixtures.
- Runtime: native frontend/backend processes; Docker for the dedicated lab workload. No required paid service or API key.

Use modules for generation, analytics, costs and execution, not networked microservices. Keep the Docker adapter separate from synthetic cloud data.

Lock API schemas before dividing UI/backend implementation: filtered overview; resource list/detail/metrics; recommendations/evidence; persistent decisions; plan/schedule/exports; alerts; lab availability/baseline/preview/apply/result/restore/history. Frontend fixtures must match those contracts and be replaced by backend responses for submission.

## 9. Five-member work split

Suggested human workstreams, not assumed assignments to specific people:

| Member | Responsibility | Handoff |
| --- | --- | --- |
| 1 | Data and optimizer | Seed data, catalog, summaries, candidate logic, safety tests. |
| 2 | API and cost planner | Schemas, persistence, cost composition, decisions, alerts, exports. |
| 3 | Overview and resources UI | App shell, filters, charts, inventory and drilldowns. |
| 4 | Recommendations and plan UI | Evidence, decisions, schedules, cost comparison, exports. |
| 5 | Local lab and submission integration | Sample workload, load harness, apply/restore, setup docs and demo script. |

Day milestones, without assuming a number of uninterrupted working hours:

1. Freeze schemas, fixtures and demo cases; connect a thin frontend/backend early.
2. Complete the core journey with persisted decisions and correct cost arithmetic.
3. Integrate alerts and lab; verify burst, memory and missing-data cases.
4. Reserve at least the final quarter of the available day for integration, setup verification, polish, README, assumptions and the demo.

No stretch work until core acceptance checks pass. If the lab is blocked, report it; do not substitute unlabeled simulation.

## 10. Definition of done

- Clean-checkout setup generates data and starts the local app without credentials or paid services.
- Every mandatory Utho workflow runs on generated data; recommendations come from backend logic.
- Filters agree across aggregates, inventory and detail pages.
- A low-use fixture receives a valid target; bursts and memory pressure block unsafe candidates; missing data causes abstention.
- Off-hours scheduling recognizes active batch windows.
- Decisions survive refresh; totals match independently calculated expectations, including combined actions and retained storage/IP costs.
- Alerts expose the triggering condition, baseline, units and time.
- The lab supplies real measurements, exact approval, apply outcome and verified restore; unavailable Docker is explained clearly.
- Synthetic inputs, assumed prices, modeled savings and measured lab results are distinguished in the UI and exports.
- Deliver source, README, assumptions sheet, architecture note, sample exports and a rehearsed 5-7 minute demo covering the problem, walkthrough, architecture and impact.

Demo: find waste -> inspect evidence -> reject a dangerously cheap plan -> accept a supported alternative -> add a dev schedule -> explain correctly composed savings and an alert -> run/restore the local experiment -> export the plan.

## 11. Stretch backlog

After core completion: forecasting with measured evaluation; GitOps proposals/PR integration when authorized; cloud emulation; richer what-if scenarios and reports. LLM chat, large-model training, carbon estimates, multi-cloud mutations and multitenant accounts are outside the core one-day build.
