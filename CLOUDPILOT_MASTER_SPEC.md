# CloudPilot — Verified FinOps Autopilot
## Master product specification for Utho / TransfiNITTe 2026

**Status:** implementation-ready consolidated brief  
**Date:** 24 October 2026  

**Timebox:** approximately 40–42 hours for the MVP; up to 5 hours CPU-side ML experimentation  
**Primary development constraint:** Windows + approximately 8 GB laptop RAM; avoid GPU requirements and heavy multi-service installations.  


> **Product positioning:** CloudPilot is a risk-aware cloud optimization control plane. It identifies waste, forecasts future workload demand, chooses **valid provider configurations** under safety constraints, tests selected changes, estimates **defensible** savings, and routes approved work through either customer-owned GitOps, a controlled direct-API mode, or manual export. It is not merely a metrics dashboard or an LLM guessing VM sizes.

---

## 1. Source of truth, problem and scope

### 1.1 Official problem statement

Source: uploaded **`TF'26 PROBLEM STATEMENTS.pdf`**, Utho section **pages 44–47** (SmartCloud Optimizer).

- Target user: infrastructure team at a mid-sized Indian SaaS company with **50–150 VMs**, deployed across **Noida, Bangalore and Mumbai**, separated into **prod, staging and dev**. The monthly cloud bill has grown **40% in six months**.
- Primary deliverable: a locally runnable working prototype converting cloud inventory, resource-usage telemetry and prices into **specific, safe, explainable and costed optimization recommendations**.
- Data can be synthetic or from real APIs. Required minimum fields: resource ID, name, type, region, environment, owner/team, vCPU, RAM, disk, creation date; **30 days of 5–15-minute** CPU, memory, disk usage/IOPS and network in/out; pricing per plan/resource.
- Include realistic steady-low, bursty, batch, weekend-idle, orphaned, and anomalous workloads.
- **Must-have screens/capabilities:** filtered resource-utilization dashboard with drilldowns; p95/p99-aware rightsizing; idle/orphan cleanup and off-hours scheduling; recommendations with exact action/reason/monthly saving/risk or confidence; interactive before/after cost totals recalculated as recommendations are accepted/rejected; alerts for anomalies, capacity and budget changes.
- **Bonus possibilities:** 30–90-day cost forecasting, what-if simulation, plain-English explanations, report/IaC exports, carbon view, roles/multitenancy.
- Deliverables: source + README, runnable MVP, dashboard, recommendation engine with savings, explicit assumptions sheet, **5–7-minute demo**.
- Scoring: **safety/effectiveness 25%; implementation 20%; transparent cost accuracy 20%; originality 15%; usability 10%; scalability/applicability 10%.** Thus 65% of score rewards core engineering and defensible economics.

### 1.2 The winning proposition

**Verified Savings:** every suggested change has an evidence packet, a safety verdict, modeled economics, optional real workload replay, and a proposed execution path. Crucial demo: **reject a cheap plan because a daily burst or application SLO would break**.

### 1.3 Explicit non-goals for the hackathon

- No production auto-apply, uncontrolled delete, or automatic manipulation of real customer infrastructure.
- No requirement for real Utho credentials, customer GitHub permissions or paid cloud services.
- No pretense that AWS emulation reproduces Utho APIs or true hardware/network performance.
- No need to self-host all of OptScale, train large neural networks, or fine-tune an LLM on 18 examples.
- No fabricated actual savings, SLO results, public pricing, provider API coverage or cloud access.

---

## 2. Product screens and end-to-end journey

1. **Overview:** spend by region/environment/team; current and modeled post-approval cost; safe savings, high-risk resources, budget trends, alerts.
2. **Resource explorer:** 100–120 VMs + volumes/IPs; filters and 30-day drilldown for CPU, memory, disk, IOPS, network, hourly heatmap.
3. **Recommendation center:** target **provider plan ID and concrete CPU/RAM/storage/network implications**, reason, monthly saving, uncertainty, safety checklist, risk classification, evidence, accept/reject.
4. **What-if simulator:** workday-only dev schedule, alternative plans, burst/traffic scenarios; before/after price recomputed with no double-counting.
5. **Alerts:** abnormal usage/cost, approaching capacity and budget overrun, with threshold/baseline, impact and timestamp.
6. **Verification laboratory:** original vs proposed limits, historical/counterfactual replay and (for one sample app) Docker+k6 measured p95 latency, errors and throttling; distinguish **simulated vs measured**.
7. **Execution center:** recommend → approve exact action → generate GitHub Terraform PR/dry run **or** controlled API dry-run **or** manual runbook → status/audit trail.
8. **Explainability/copilot (P1):** natural-language read-only explanations grounded in evidence; model cannot invent statistics or perform mutation without backend-enforced authorization.

Recommended demo story: 8-vCPU production API with low mean utilization → 2-vCPU candidate appears cheaper but fails peak/SLO test → 4-vCPU candidate passes → show risk and monthly savings → user approval → Terraform PR/dry run → post-change verification workflow. Also show one `insufficient_data` abstention.

---

## 3. Architecture and stack

```text
Data sources: SyntheticUthoAdapter | Bitbrains/Materna import | Utho read-only adapter (optional)
       ↓
Ingestion + normalization (FastAPI / Pydantic) → DuckDB + Parquet metrics; SQLite metadata/events
       ↓
Feature engine (lags, seasonal peaks, p95/p99, missingness, capacity, dependencies)
       ├── Baselines and ML (Ridge, Random Forest, LightGBM quantile)
       ├── Valid plan catalog + constrained cost optimizer
       ├── Hard policy gates + probabilistic scenario-risk estimates
       └── Verification: simulated replay + Docker/k6 SLO benchmark
       ↓
Recommendations (evidence, source, model version, risk, savings, action state)
       ↓
React UI + what-if simulations + read-only AI explanation
       ↓
Explicit approval & controlled executor
       ├── GitOps: customer-authorized GitHub App → branch/PR → CI Terraform plan
       ├── Direct API: ONLY unmanaged resources, permitted adapter & approval
       └── Export: detailed manual runbook / script / IaC proposal
       ↓
Audit → monitor/verify outcomes → compare predicted and realized savings
```

**Preferred implementation:** React + Vite + TypeScript + Tailwind + Recharts; Python FastAPI/Pydantic; Pandas/NumPy/scikit-learn + LightGBM; DuckDB+Parquet and SQLite; Docker Compose; pytest; k6. OR-Tools optional for portfolio-wide optimization; Redis/Postgres/Kubernetes are **not** required.

Use typed, swappable interfaces:
- `CloudInventoryAdapter`, `MetricsAdapter`, `PricingAdapter`, `ExecutionAdapter`.
- `SyntheticUthoAdapter` is first-class and fully functional without secrets.
- `FlociAwsAdapter` is **AWS control-plane test only**; do not pretend it speaks native Utho API.
- `UthoAdapter` is an optional read-only integration, with testable interface and no mandatory API key.

Suggested folders: `frontend/`, `backend/app/api/`, `backend/app/engine/`, `backend/app/ml/`, `backend/app/adapters/`, `backend/app/models/`, `backend/tests/`, `data/generate_data.py`, `data/catalog/`, `experiments/`, `infra/demo-terraform/`, `docs/`, `docker-compose.yml`, `README.md`.

---

## 4. Data strategy (real telemetry + synthetic demo + supervised labels)

### 4.1 Real datasets considered

| Dataset / access | Scale / fields | Decision |
|---|---|---|
| [Bitbrains GWA-T-12 fastStorage](https://atlarge-research.com/gwa-t-12/) ([ZIP](https://atlarge-research.com/gwa-traces/gwa_t_12_fastStorage.zip)) | ~128 MB; 1,250 VMs, ~5-minute CPU provisioned/used, memory provisioned/used, disk **throughput**, network | **Primary real ML workload data.** Sample ~100 VMs, ~30 days at 15 minutes, keep interval **max** as well as means. |
| [Preprocessed Bitbrains 100 FNvs](https://github.com/alhamedy/Dataset-used-to-build-the-time-series-prediction-models) | Two GitHub CSVs, ~14 MB, 100 VMs, CPU/memory at 15-minute resolution | Quick prototype; loses disk/network. |
| [GWA-T-13 Materna](https://atlarge-research.com/gwa-t-13/) | ~145 MB; enterprise utilization / VM specs / I/O | Optional **external-validation** subset after normalization. |
| [Bitbrains Rnd](https://atlarge-research.com/gwa-t-12/) ([ZIP](https://atlarge-research.com/gwa-traces/gwa_t_12_rnd.zip)) | ~156 MB, 500 VMs, complementary workloads | Optional extra generalization. |
| [Azure Public Dataset V1](https://github.com/Azure/AzurePublicDataset/blob/master/AzurePublicDatasetV1.md) | ~78.5 GB compressed, ~1.25 billion 5-min CPU observations | **Do not download whole dataset.** CPU time series only; lacks corresponding complete VM-level RAM/disk/network utilization. |
| [Azure VM Noise 2024](https://github.com/Azure/AzurePublicDataset/blob/master/AzureVMNoiseDataset2024.md) | ~277 MB benchmark variability | Optional performance-risk research, not main VM labels. |
| [Alibaba 2017 Cluster Trace](https://github.com/alibaba/clusterdata/tree/master/cluster-trace-v2017) | CPU/memory/disk and scheduling; only 12 hours of disclosed usage in original trace | Optional workload/scheduling stress test, not 30-day forecasting. |
| [Processed Google Cluster CPU subset](https://zenodo.org/records/6979672) | ~2.4 MB CPU-only | Tiny forecasting sanity check. |

**Limits to declare:** Bitbrains disk columns describe read/write throughput, **not used disk bytes or disk IOPS**. Add separately labeled synthetic disk-capacity/IOPS fields for demo; never present them as measured Bitbrains labels. Source and real/synthetic provenance accompany every sample.

### 4.2 Labeled optimization / supervised learning datasets

| Source | What it labels | Proper use |
|---|---|---|
| [Synthesized Cloud Optimization Recommendations (HF)](https://huggingface.co/datasets/ameau01/synthesized-cloud-optimization-recommendations) | **18** hand-crafted scenarios: telemetry, Terraform, actions, reasoning, risk, saving; AWS nomenclature | Schema inspiration and **separate** decision-agent eval; too few for serious SFT. |
| [Multi-Cloud Resource Dataset (Kaggle)](https://www.kaggle.com/datasets/freshersstaff/multi-cloud-resource-dataset) | Approximately 1,000 labeled `scale_up/scale_down/no_action` cases; CPU, RAM, VM specs and telemetry | Small prototype **only**: labels/plan names may be inconsistent and are not verified as safe. |
| [Example CSV + XGBoost code](https://github.com/dhanushmb/Intelligent-Cloud-Cost-Optimization-Forecasting-System-/) | `data-importer-service/multi_cloud_dataset.csv`, `ml-analytics-service/recommendation.py` | Code/label-format reference; inspect and warn about questionable labels. |
| [AWS Compute Optimizer export documentation](https://docs.aws.amazon.com/compute-optimizer/latest/ug/exporting-recommendations.html) | Provider-generated recommendations available within an authorized account | Potential future real teacher labels; **not** a public ready-to-download dataset. |
| [Lorentz: Learned SKU Recommendation Using Profile Data](https://www.microsoft.com/en-us/research/publication/lorentz-learned-sku-recommendation-using-profile-data/) | Research method for learning allocation from profiles, capacity labels and customer feedback | Research inspiration; **not** a downloadable labeled Utho dataset. |

**Our labeled set:** create teacher/reference-policy labels from real workload histories + a **versioned Utho-like plan catalogue**. For each time window, evaluate all valid plans against *future* replayed demand/constraints to derive a reference safe plan/action, saving, and risk. In training examples, features can only use data available **before** the future window. Label as **algorithm-derived / synthetic**, not proven production optimal. Include `upsize`, `downsize`, `schedule`, `no_action`, `review_orphan`, `defer_insufficient_data` where logically justified.

**Key ML distinction:** XGBoost/Random Forest classifiers are **supervised learning**, not LLM SFT. LLM supervised fine-tuning would need many more curated input→explanation/decision examples and is **out of MVP scope**. A model imitating teacher labels cannot automatically be claimed better than its teacher.

### 4.3 Synthetic Utho demo estate

- Deterministically generate **120 VMs × 30 days × 96 samples/day = 345,600 VM observations**, plus block volumes, unattached disks, public IPs and 6-month billing snapshots; all keyed by resource ID.
- Regions: Noida, Bangalore, Mumbai; tags: prod/staging/dev; owner/team; vCPU, RAM, disk, plan, created date, criticality, management mode (`terraform`/`unmanaged`/`unknown`), dependency edges.
- Workload patterns: steady-low, dangerous burst peaks, nightly batch jobs, weekday-only dev, genuine anomaly, orphaned volume/IP, memory bound, network/disk bound, insufficient telemetry, realistic cost spikes.
- Separate `observed`, `derived`, `simulated`, `assumed` in schema. Version the price catalogue and assumptions. Use Utho catalogue fixtures and/or documented lookup; never hardcode unsupported arbitrary plan IDs as real provider plans.
- Keep disk occupancy, IOPS, SLO traces, owner/dependencies and cost billing assumptions **synthetic** unless observed from connected sources.
- Use reproducible seeded generator, small Parquet and CSV fixtures; do not ship a 128 MB archive inside repo without need.

---

## 5. ML engine: forecasting vs direct recommendation

**Preferred design: predictive model + constrained optimizer + independent safety validation.** Do **not** directly regress arbitrary numbers of vCPU, GB RAM and storage, because CSPs offer discrete, region-dependent plans and resizing may be restricted.

1. **Features:** current allocatable cores/RAM/disk, CPU cores used / pct, memory GB used, disk read/write, network traffic, p50/p95/p99/max, temporal lags, rolling maxima, hourly/weekly cyclical features, missingness, service/env/criticality, forecast horizon.
2. **Targets:** e.g., maximum CPU cores used / max RAM GB / maximum throughput during *next hour* (or day), with conservative prediction intervals / high quantiles.
3. **Comparison:** rolling-p99 / seasonal naive baseline; Ridge; shallow RandomForest; **LightGBM quantile** (preferred); XGBoost optional; small MLP and LSTM/Transformer only if time remains. Fit per-resource CPU and RAM demand first; do not require GPU.
4. **Split:** chronological train days 1–21, validation 22–25, test 26–30 with gap/purge for overlapping target windows; hold out entire VM IDs for a separate cold-start/generalization test. No random interleaving of the same VM timestamps across train/test.
5. **Evaluation:** pinball loss / quantile empirical coverage, peak under-prediction rate, constraint breach rate, cost of chosen plan, oracle regret under synthetic future replay, inference runtime/memory. Compare to **simple historical-p99 rule** and show when ML abstains/underperforms.
6. **Training machine:** 8 GB RAM; sample ~50–100 VMs / 15-minute aggregates; batch CPU training; cap `n_jobs`; expected experiment wall-clock budget ~5 hours (not a guaranteed runtime).

**Candidate objective:** among provider-valid plans `p`, minimize `monthly_cost(p) + lambda * modeled_risk(p) + migration_cost(p)` subject to hard CPU/RAM/disk/network/IOPS/SLO/compatibility constraints. Enumerate catalogue plans; OR-Tools only if a multi-VM budget/dependency problem requires it.

**CPU sanity approximation (same architecture family only):** `predicted_cpu_pct = observed_cpu_pct * current_vcpu / target_vcpu`. It ignores scheduling, contention and architectural differences; require benchmark when possible. Never blindly downsize based on mean CPU or an LLM's guess.

---

## 6. Optimization engine and economics

**Supported actions:** VM `upsize/downsize` to an existing plan, non-prod scheduled stop/start, investigate idle/possibly delete, cleanup unowned/unattached disks/IPs after ownership verification, and `no_action/defer`. Show network/storage improvements where *provider capacity and charge models support them*; otherwise label them as analysis, not executable promises.

**Checks on each candidate:** CPU high quantile and short peaks; physical RAM GB; disk usage/headroom/growth and separately IOPS; network bandwidth; valid SKU for region; architecture/family/license compatibility; inter-resource dependency graph; environment criticality; telemetry coverage; billing type; scheduled dependencies; rollback path; cloud/provider action limitations.

**Cost model:** exact versioned catalogue prices where available; separate compute, block volumes, IP, backups and egress; respect minimum billing terms and actual stop-instance charging rules. Calculate `current monthly projected spend - recommended projected spend - one-time amortized change cost` as appropriate; show gross monthly saving separately from one-time migration costs. Never assume stopping a monthly-billed VM stops charges. Do not double-count resize plus schedule or overlapping recommendations. Accept/reject instantly recomputes **accepted portfolio savings**; also keep *potential unapproved* separate.

**Approval card required:** resource + exact current/target plan and specs, action prerequisites, measured utilization and forecast, evidence freshness, modeled price and monthly saving, `safe/review/blocked/insufficient_data`, reasons, confidence/risk explanation, approval/rollback, latest plan & IaC revision IDs.

---

## 7. Risk and verification design

**Tier A — non-negotiable hard gates:** missing/stale data, incompatible SKU, memory/storage/IOPS/network breach, unsupported disk shrink, production shutdown without policy, unresolved IaC drift, bad health/SLO results, missing owner approval. Hard failures veto AI/ML recommendations.

**Tier B — probabilistic scenarios:** time-block bootstrap future load preserving day/week rhythms, plus 2× launch traffic, month-end batch, high memory and network spikes. Compute empirical scenario fraction exceeding capacity/SLO; report it as **modeled breach frequency**, not actual downtime probability. Risk score is a documented heuristic unless calibrated with real incident labels.

**Tier C — measured workload replay:** run one sample web/API app with Docker CPU/RAM restrictions; drive traffic with **k6**; record measured p95 latency, error %, CPU throttling and OOM / container restarts. Test baseline and at least two candidate limits. Docker replay is *not* proof of identical behavior on specific Utho processors/disks/networks.

**Optional Jev:** TypeSafe Jev gives typed decisions/probabilities; use it only for **contextual review routing** (`routine`, `senior_SRE`, `needs_information`) or explanation ranking. Jev scores cannot override hard gates and are not calibrated outage probabilities. Core works without an API key.

**Differentiator:** a downloadable **Safety Proof / Verified Savings evidence packet** showing every passed, failed and uncertain check plus test provenance.

---

## 8. Cloud emulation, cloud APIs and IaC reality

**Floci** ([source](https://github.com/floci-io/floci)) and **LocalStack** ([source](https://github.com/localstack/localstack), [docs](https://docs.localstack.cloud/)) are AWS-shaped cloud emulators. **Choose Floci as optional primary AWS control-plane integration/test, LocalStack as fallback**; don't run both by default. These test API operations / inventory / mock cloud lifecycle, not performance of Utho VMs. Validate specific APIs before promising exact coverage. LocalStack's current licensing/features should be checked before use. **'LoCo' / 'LocaStack' were not unambiguously identified; do not add unknown dependencies.**

For real workload validation, use **Docker + k6** independently; optional **Prometheus** to collect measured metrics.

**Utho Terraform provider:** [uthoplatforms/terraform-provider-utho](https://github.com/uthoplatforms/terraform-provider-utho) includes [`utho_cloud`](https://github.com/uthoplatforms/terraform-provider-utho/blob/main/docs/resources/cloud.md), [`utho_cloud_resize`](https://github.com/uthoplatforms/terraform-provider-utho/blob/main/docs/resources/cloud_resize.md), [`utho_cloud_power`](https://github.com/uthoplatforms/terraform-provider-utho/blob/main/docs/resources/cloud_power.md), [`utho_cloud_snapshot`](https://github.com/uthoplatforms/terraform-provider-utho/blob/main/docs/resources/cloud_snapshot.md). **Changing `utho_cloud.planid` directly can force instance replacement**; the dedicated resize operation must be examined. Documented resizing requires shutdown first; `ramcpu` vs `full`; disk may not shrink/reverse, and only valid DC plans apply. `utho_cloud_resize` may itself need special lifecycle handling; test it before generating an automatic apply proposal.

**Correct GitOps ownership:** Utho as a CSP has **no automatic access to a customer's Terraform repository**. GitOps only works if the **customer authorizes a GitHub App for selected repos** or deploys a customer-owned execution connector. Agent opens a branch and PR with approved change; customer's CI runs a Terraform plan; an authorized, customer-controlled runner applies it. Terraform config in Git is declared intent, Terraform state tracks managed resource instances; direct console/API changes to Terraform-managed infrastructure cause drift.

**Three execution modes:**
- **GitOps-managed:** customer-authorized repo → exact approved diff → PR → CI plan/policy → customer review → permitted apply → post-change verification. No agent direct mutation.
- **Unmanaged/direct API:** if management mode is confirmed *unmanaged*, with scoped credentials and explicit action-bound approval, backend executor may call Utho API. Hackathon: **simulated/dry-run only**.
- **Manual/export:** create runbook, scripts/snippets, prerequisites, verification steps and rollback for users without repo/API connection.

**Security:** MCP is tool-call plumbing, **not** authorization. Backend restricts tool list, credentials, resource/plan/tenant scope, signed approval bound to action+resource+config+evidence version, expiries, audit log, idempotency, drift/revision recheck, and last-minute plan review. No blanket shell execution or model-owned secrets; no direct production destructive apply in demo. Customer-hosted outbound executor is a future enterprise option to avoid central credential custody.

---

## 9. Existing market / OSS benchmark

| Tool | Already solves | How CloudPilot differs in scope |
|---|---|---|
| [Hystax OptScale](https://github.com/hystax/optscale) | Multi-cloud costs, VM rightsizing, idle/shutdown schedules, budgets, pools, allocations | Evidence-backed counterfactual replay + transparent workflow PR for a smaller Utho estate. |
| [Robusta KRR](https://github.com/robusta-dev/krr) | Kubernetes percentile rightsizing | Utho-like VM plans + GitOps decision/verification. |
| [CAST AI](https://cast.ai/) | Automated cloud/Kubernetes infrastructure optimization | Hackathon-grade transparent risk evidence in VM context. |
| [Kubecost](https://www.kubecost.com/) / [OpenCost](https://www.opencost.io/) | Kubernetes cost allocation | VM, storage, IP and provider plan optimization. |
| [Infracost](https://www.infracost.io/) | Terraform cost diffs | Learn from usage before generating a Terraform change. |

**OptScale implementation lessons (inspected):**
- [`rightsizing_instances.py`](https://github.com/hystax/optscale/blob/integration/bumiworker/bumiworker/modules/recommendations/rightsizing_instances.py): VM rightsizing with default q99 metric and 80% target, enumerating compatible flavors and calculating savings.
- [`rightsizing_base.py`](https://github.com/hystax/optscale/blob/integration/bumiworker/bumiworker/modules/rightsizing_base.py): approximate CPU need = `ceil(current_vcpu * current_cpu_p99_percent / 80)`, plan catalogue match and projected CPU statistics.
- [`instances_for_shutdown.py`](https://github.com/hystax/optscale/blob/integration/bumiworker/bumiworker/modules/recommendations/instances_for_shutdown.py): 14-day default, 5% CPU and low network threshold, inactive weekday/time windows, scheduling economics.
- **Do not** deploy full OptScale as our MVP: repository documents at least **16 GB RAM** for its evaluation setup, above our laptop constraints. Study code and build a focused implementation.

---

## 10. Fifteen additional product ideas (scope-ranked)

| # | Idea | Priority | Description / demo |
|---|---|---|---|
| 1 | SLO-aware optimization | P0 | Reject candidates that violate latency/errors despite savings. |
| 2 | Counterfactual replay | P0 | Replay a daily burst on 2/4/8 vCPU scenarios. |
| 3 | Savings confidence intervals | P0 | Model a plausible savings range with explicit cost assumptions. |
| 4 | Portfolio Pareto frontier | P1 | Compare conservative/balanced/aggressive cost-risk tradeoffs. |
| 5 | Shadow mode | P0/P1 | Historic what-would-have-happened replay with no mutation. |
| 6 | Rollback triggers | P1 | Failure thresholds and rollback-ready procedure. |
| 7 | Change-conflict detection | P0 | Block stale approvals / incompatible Terraform revisions. |
| 8 | Dependency blast-radius graph | P1 | Protect apparently idle critical dependencies. |
| 9 | Per-environment risk budgets | P1 | Stricter prod, tailored dev policy. |
| 10 | Capacity stress scenarios | P0 | Future 2× traffic, month-end spikes, growth. |
| 11 | Feedback learning | P1 | Compare predicted and measured savings after change. |
| 12 | Inferred owners | P2 | Guess owner of untagged disks with human verification. |
| 13 | Data-quality abstention | P0 | Refuse recommendations without adequate evidence. |
| 14 | Unit economics | P2 | Cost per customer/request, not just VM cost. |
| 15 | Topology/network optimizer | P2 | Egress/region/IP/load-balancer tradeoffs. |

**Core novelty to prioritize:** #1, #2, #7, #10, #13 plus verified evidence packet and GitOps PR. Treat the rest as visible backlog, not a 42-hour promise.

---

## 11. API and state contracts

Proposed REST:

```text
GET    /api/health
GET    /api/summary
GET    /api/resources?region=&environment=&team=&type=
GET    /api/resources/{resource_id}/metrics?start=&end=
GET    /api/plans?region=
GET    /api/recommendations?risk=&status=
GET    /api/recommendations/{id}
PATCH  /api/recommendations/{id}    {decision: accept|reject, actor, evidence_version}
POST   /api/simulate                {action_ids, schedule, demand_multiplier}
POST   /api/verify                  {recommendation_id, mode: replay|benchmark}
GET    /api/alerts
GET    /api/ml/benchmarks
POST   /api/changes/propose         {recommendation_id, execution_mode}
GET    /api/changes/{id}
```

Every recommendation stores: `id`, `resource_id`, `observed_window`, `features_version`, `model_name/version`, `catalogue_version`, `current_plan`, `proposed_plan`, `action_type`, `cost_before`, `cost_after`, `estimated_savings`, `risk_class`, `hard_gate_results`, `scenario_breach_rate`, `verification_result`, `provenance`, `assumptions`, `status`, `approved_by/at`, `terraform_revision`, `PR URL if created`.

Lifecycle: `DETECTED → ANALYZED → VERIFIED → PROPOSED → APPROVED → PR_OPEN / DRY_RUN → APPLIED → MONITORED`, with `REJECTED`, `BLOCKED`, `INSUFFICIENT_DATA`, `FAILED`, `ROLLED_BACK`. MVP must implement all *relevant demo-state transitions*; APPLIED/MONITORED may be simulated, never falsely represented as live.

Read-only MCP tools: `list_resources`, `get_metrics`, `get_candidate_plans`, `run_optimization`, `run_risk_assessment`, `simulate_change`, `get_alerts`; controlled action tool: `create_change_proposal` and `open_pr` **only after approval**. Keep model explanations optional and evidence-bound.

---

## 12. Mandatory implementation tests and measurable acceptance criteria

**Functional:**
- Reproducible `make`/Python generator produces 120 VMs and exactly 30 days of 15-min samples, plus anomalies, orphans, 6-month bills and realistic resource metadata.
- Dashboard filters, drilldowns, graphs, recommendations, simulator and alerts work locally with no cloud token.
- Every recommendation specifies an exact valid catalogue plan/action and safety/cost rationale; `accept/reject` changes totals consistently.
- At least one high-mean-vs-peak counterexample blocked; memory-bound VM blocked; missing-data abstention; non-prod shutdown preview; orphan disk requires owner verification.
- Combined schedule+resize does not double-count savings; fixed-rate/minimum-term billing cannot be canceled magically by stop.
- Constrained optimizer honors same-region plan availability, storage limitations and high-quantile demand; no unsupported disk shrink.
- ML benchmark charts compare baseline vs at least **Ridge and LightGBM** with test-set upper-tail coverage, unsafe-candidate rate and simulated realized saving. If ML is worse, system must prefer baseline.
- One Docker+k6 test actually measures application p95 latency and HTTP error rate at original vs reduced container limits; dashboard identifies results as local-container results.
- One read-only Floci test or reproducible API mock, with provider coverage caveat. Emulator optional and not required to launch app.
- An approved proposal produces **validated Terraform diff/dry-run** in demo repo; optionally opens a **real PR only if demo repo credentials are configured**. Never require customer repo creds.
- No mutating provider operation without exact approval and authorization; secrets never recorded in logs.

**Quality:** backend pytest suite, frontend build, typed response schemas, README with Windows PowerShell and optional Docker instructions, local seed data, sample config `.env.example`, explanation of unsupported APIs, assumptions sheet, trace provenance and limitations, 5–7-minute demo script.

**Prioritized cut line:** P0 = fully working metrics, safe rules, cost, alerts, simulator, ML baseline comparison, approval/evidence; P1 = Docker replay + GitOps PR + Floci proof + explanation AI; P2 = Jev, forecasting 90 days, RL/deep models, carbon, multi-tenant, full real Utho account integration.

---

## 13. Hackathon timeline and team assignments

| Time | Goal | Owner (4-person split) |
|---|---|---|
| 0–4h | Project skeleton, Pydantic/API contracts, sample dataset schema, frontend routes, agreed demo cases | All |
| 4–12h | Reproducible data, pricing & deterministic rightsizing, inventory and metrics UI | Data/ML, Backend, Frontend |
| **Hour 12 gate** | Rules produce correct price, safe/unsafe and no-action recommendations | Backend/Data |
| 12–20h | ML training comparison, candidate plan search, risk gates and savings model | ML/Backend |
| **Hour 20 gate** | Show no ML degradation or default to transparent baseline | ML |
| 20–28h | Scenario replay + one Docker/k6 workload; approve → Terraform proposal; optional Floci | Infra/Backend |
| **Hour 28 gate** | End-to-end observation → decision → dry-run change path demonstrated | All |
| 28–34h | Wire UI/API, harden approval states, add actionable alert/anomaly and exports | All |
| **Hour 34 gate** | Feature freeze, full acceptance test pass | All |
| 34–42h | Documentation, reproducible install, 5–7-minute demo, fallback recording, polish | All |

Team roles: **(1) Backend + optimization; (2) Frontend + UX; (3) Data + ML + experiment; (4) Infra + integrations + quality/pitch**. Integrate the summary/resource API by hour 8–10; do not wait until the end.

**Suggested effort split:** ~45% optimization/testing, 25% UI, 20% GitOps/integration, 10% docs/demo. Implementation can overlap by member.

---

## 14. Resource library (everything discussed; main URLs)

### Official brief, Utho and IaC
- **Hackathon source:** `TF'26 PROBLEM STATEMENTS.pdf`, pages 44–47, Utho section (uploaded in chat; not publicly linked).
- [Utho public pricing](https://utho.com/pricing) — current values must be read/verified, not assumed.
- [Utho Terraform provider](https://github.com/uthoplatforms/terraform-provider-utho) — `docs/resources/cloud.md`, `cloud_resize.md`, `cloud_power.md`, `cloud_snapshot.md`, `docs/data-sources/cloud_plans.md`.
- [Terraform docs](https://developer.hashicorp.com/terraform/docs); [OpenTofu](https://opentofu.org/docs/); [GitHub Apps](https://docs.github.com/en/apps); [GitHub Actions](https://docs.github.com/en/actions); [Model Context Protocol](https://modelcontextprotocol.io/).

### Competitors and implementation lessons
- [OptScale](https://github.com/hystax/optscale), [OptScale rightsizing base](https://github.com/hystax/optscale/blob/integration/bumiworker/bumiworker/modules/rightsizing_base.py), [OptScale VM rightsizing](https://github.com/hystax/optscale/blob/integration/bumiworker/bumiworker/modules/recommendations/rightsizing_instances.py), [OptScale shutdown scheduler](https://github.com/hystax/optscale/blob/integration/bumiworker/bumiworker/modules/recommendations/instances_for_shutdown.py).
- [Robusta KRR](https://github.com/robusta-dev/krr), [CAST AI](https://cast.ai/), [Kubecost](https://www.kubecost.com/), [OpenCost](https://www.opencost.io/), [Infracost](https://www.infracost.io/).

### Datasets and ML research
- [Bitbrains fastStorage + Rnd documentation](https://atlarge-research.com/gwa-t-12/); [fastStorage ZIP](https://atlarge-research.com/gwa-traces/gwa_t_12_fastStorage.zip); [Rnd ZIP](https://atlarge-research.com/gwa-traces/gwa_t_12_rnd.zip); [Materna](https://atlarge-research.com/gwa-t-13/).
- [Preprocessed Bitbrains CPU/RAM CSVs](https://github.com/alhamedy/Dataset-used-to-build-the-time-series-prediction-models).
- [Azure V1](https://github.com/Azure/AzurePublicDataset/blob/master/AzurePublicDatasetV1.md); [Azure VM Noise](https://github.com/Azure/AzurePublicDataset/blob/master/AzureVMNoiseDataset2024.md); [Alibaba 2017](https://github.com/alibaba/clusterdata/tree/master/cluster-trace-v2017); [Google CPU subset](https://zenodo.org/records/6979672).
- [HF synthetic optimization scenarios](https://huggingface.co/datasets/ameau01/synthesized-cloud-optimization-recommendations); [Kaggle Multi-cloud Resource dataset](https://www.kaggle.com/datasets/freshersstaff/multi-cloud-resource-dataset); [sample labeled CSV + XGBoost classifier](https://github.com/dhanushmb/Intelligent-Cloud-Cost-Optimization-Forecasting-System-/).
- [AWS Compute Optimizer recommendation export](https://docs.aws.amazon.com/compute-optimizer/latest/ug/exporting-recommendations.html); [Microsoft Lorentz paper](https://www.microsoft.com/en-us/research/publication/lorentz-learned-sku-recommendation-using-profile-data/).

### Emulator, verification and AI
- [Floci](https://github.com/floci-io/floci); [LocalStack](https://github.com/localstack/localstack) and [licensing docs](https://docs.localstack.cloud/aws/licensing/); [Docker](https://docs.docker.com/); [k6](https://grafana.com/docs/k6/latest/); [Prometheus](https://prometheus.io/docs/).
- [Jev reference/ecosystem](https://jevaihub.com/) and [TypeSafe AI](https://typesafe.ai/); [FastAPI](https://fastapi.tiangolo.com/); [LightGBM](https://lightgbm.readthedocs.io/); [DuckDB](https://duckdb.org/docs/).

---

## 15. Decision log and honest research-status notes

- **Chosen:** mixed *real workload ML + synthetic Utho demonstration + algorithm-derived supervised labels*, not gigantic Azure downloads.
- **Chosen:** quantile demand prediction + valid-plan optimization + conservative hard gates; compare with rule/p99 baselines.
- **Chosen:** dynamic verified-savings audit trail; customer-owned GitOps **when authorized**; manual/direct adapter fallback.
- **Chosen:** Floci **optional** AWS emulation, Docker+k6 actual local resource-limit experiment. Floci is not a Utho simulator or hardware performance verifier.
- **Deferred:** Jev and LLM SFT. Jev is optional review triage, not outage risk truth. 18 HF scenarios cannot credibly train a general-purpose optimizer alone.
- **Deferred:** customer-hosted executor, true Utho API live changes, 90-day forecast, multi-tenant RBAC, advanced carbon/energy calculation, topology optimization, large-neural-model experiment.
- **Research claims to recheck before claiming victory:** current Utho plan pricing and billing/resize behavior; Floci and/or LocalStack API fidelity; GitHub App authorization; whether Terraform provider resize is reproducible in demo; external dataset licenses/attribution and actual delivered archives; out-of-sample ML gains; empirical load-test findings.
- **Demo results must be from code, not made-up accuracy or savings.** Clearly label synthetic inputs, simulated futures and measured Docker/k6 performance.

---

## 16. Final demo and handoff checklist

**Demo beats (6–7 minutes):** problem 0:00–0:40 → dashboard/inventory 0:40–1:30 → safe resize 1:30–2:30 → dangerous burst rejection 2:30–3:20 → ML benchmark / risk evidence 3:20–4:10 → what-if costs and alert 4:10–5:00 → approve + PR/dry-run 5:00–6:00 → measured replay, limitations, next steps 6:00–6:30.

**Deliver:** bootable local app; `README.md`; seed generator; checked-in tiny demo fixtures; model training script & results; transparent pricing/assumptions sheet; `docs/architecture.md`; `docs/data_provenance.md`; `docs/safety_and_limits.md`; `docs/demo_script.md`; acceptance tests; optional Docker Compose; screenshots/video fallback. Cite Bitbrains/other dataset rights appropriately.

**One-sentence pitch:** *“CloudPilot doesn't just show cloud waste: it finds a lower-cost valid configuration, tests how that change affects workload and SLO risk, and safely proposes the change through the customer's preferred infrastructure workflow.”*
