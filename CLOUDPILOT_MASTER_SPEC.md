# CloudPilot — Verified FinOps Autopilot
## Complete Product, AI Agent, ML, Infrastructure & Implementation Specification

**Utho / TransfiNITTe 2026**

**Date:** 24 October 2026\
**Implementation window:** 40–42 hours, with approximately five hours allocated to CPU-side ML experimentation\
**Team:** Four contributors\
**Development environment:** Windows, approximately 8 GB RAM\
**Delivery:** Working local prototype, complete source code, reproducible experiments, infrastructure workflows, documentation, and a 5–7-minute demonstration

---

## 1\. Product Vision

CloudPilot is an AI-assisted cloud FinOps optimization control plane that discovers infrastructure waste, forecasts demand, identifies cost-saving opportunities, validates proposed configurations, calculates defensible savings, and prepares approved infrastructure changes for execution.

It combines deterministic optimization, machine learning, scenario simulation, workload benchmarking, cloud-provider integrations, an MCP-enabled agent, and customer-controlled infrastructure automation.

Every recommendation includes its supporting evidence, target configuration, pricing assumptions, safety checks, risk assessment, and execution history.

**Product objective:** Convert cloud optimization opportunities into measurable, explainable, validated, and auditable infrastructure changes.

## 2\. Problem Statement and Evaluation Objectives

The product targets an infrastructure team at a mid-sized Indian SaaS company managing 50–150 VMs across Noida, Bangalore, and Mumbai, with production, staging, and development environments.

The reference problem describes a cloud bill that has increased 40% over six months.

The prototype accepts synthetic data, public workload traces, or connected provider data and produces concrete optimization recommendations.

### Required capabilities

- Filterable resource-utilization dashboard with historical drilldowns.
- CPU and memory rightsizing based on p95, p99, peaks, and future demand.
- Idle resource detection, orphan cleanup review, and non-production scheduling.
- Exact candidate plan, projected monthly savings, explanation, confidence, and risk.
- Interactive before-and-after cost calculations.
- Budget, utilization, anomaly, and capacity alerts.
- Reproducible data generation, documented assumptions, and a runnable local application.

### Additional capabilities

- Thirty- to ninety-day cost forecasting.
- Workload what-if simulation.
- Natural-language explanations.
- Terraform and report exports.
- Carbon and energy analysis.
- Role-based access control and multi-tenancy.
- MCP-based agent orchestration and controlled tool execution.
- Automated evidence generation, approval, and infrastructure proposals.

### Evaluation alignment

| Evaluation dimension | CloudPilot implementation |
| --- | --- |
| Safety and effectiveness — 25% | Policy gates, demand replay, dependency checks, benchmark validation |
| Implementation — 20% | Working application, APIs, agent tools, optimizer, integrations |
| Cost accuracy — 20% | Versioned prices, billing rules, savings reconciliation |
| Originality — 15% | Verified Savings, MCP orchestration, SLO-aware counterfactual testing |
| Usability — 10% | Interactive dashboards, explanations, approvals |
| Scalability and applicability — 10% | Adapter architecture, modular services, multi-cloud data model |

## 3\. End-to-End Product Experience

CloudPilot provides the following connected workspaces.

1. **Overview:** Spend by region, environment, and team; modeled savings; budget trends; risk indicators and alerts.
2. **Resource Explorer:** Inventory, filters, CPU, memory, disk, IOPS, network, and historical utilization heatmaps.
3. **Recommendation Center:** Exact current and proposed configurations, action, reason, cost impact, risk, evidence, and accept/reject controls.
4. **What-if Simulator:** Alternative plans, workday schedules, traffic multipliers, future demand, and portfolio cost comparisons.
5. **Alerts:** Abnormal cost or utilization, capacity thresholds, and budget forecasts.
6. **Verification Laboratory:** Historical replay, counterfactual scenarios, Docker/k6 benchmarks, latency, errors, throttling, and restart metrics.
7. **Execution Center:** Approval, Terraform proposals, GitHub pull requests, API dry runs, manual runbooks, audit records, and verification.
8. **AI Copilot:** Natural-language questions, evidence-grounded explanations, recommendation summaries, and review routing.
9. **Agent Activity and Audit:** MCP tool invocations, decisions, evidence references, authorization results, and execution state.
10. **Reports and Governance:** Exportable evidence packets, pricing assumptions, usage reports, access controls, and change history.

### Demonstration scenario

An eight-vCPU production API appears underutilized on average. The optimizer evaluates two- and four-vCPU alternatives. Peak demand and application benchmarks expose the risk of the smaller candidate. A validated alternative is presented with its savings, evidence, and approval requirements. The user approves a Terraform proposal, reviews its dry-run result, and examines the verification workflow.

The demo also includes an insufficient-data recommendation, a scheduled development workload, an orphaned volume requiring ownership verification, and an anomaly alert.

## 4\. Complete Architecture

text

```
Data Sources
  ├── Synthetic Utho Adapter
  ├── Bitbrains / Materna Dataset Imports
  ├── Utho Read-Only API Adapter
  └── AWS-Compatible Emulator / API Mock
                |
                v
Ingestion and Normalization
  ├── FastAPI / Pydantic
  ├── DuckDB / Parquet
  └── SQLite Metadata and Events
                |
                v
Feature Engineering
  ├── Temporal Lags and Rolling Statistics
  ├── p95 / p99 / Peaks / Missingness
  ├── Capacity and Dependency Features
  └── Workload Classification
                |
                v
Analytics and Decision Services
  ├── Historical Percentile Baselines
  ├── Ridge / Random Forest / LightGBM
  ├── Optional XGBoost / Neural Models
  ├── Valid Provider Plan Catalogue
  ├── Constrained Cost Optimizer
  ├── Hard Safety Gates
  └── Scenario Risk Assessment
                |
                v
Verification and Evidence
  ├── Historical Counterfactual Replay
  ├── Docker + k6 Workload Benchmark
  ├── Optional Prometheus Metrics
  └── Verified Savings Evidence Packet
                |
                v
MCP Agent and Application API
  ├── Read-Only Resource and Metric Tools
  ├── Optimization and Simulation Tools
  ├── Risk and Evidence Tools
  ├── Explanation / Review Routing
  └── Approval-Bound Change Tools
                |
                v
React + Vite + TypeScript UI
                |
                v
Explicit Authorization and Execution
  ├── Customer-Owned GitOps / GitHub PR
  ├── Controlled Direct Provider API
  └── Manual Runbook / Script / IaC Export
                |
                v
Audit → Monitoring → Verification → Feedback
```

### Technology stack

- **Frontend:** React, Vite, TypeScript, Tailwind CSS, Recharts.
- **Backend:** Python, FastAPI, Pydantic.
- **Data:** Pandas, NumPy, DuckDB, Parquet, SQLite.
- **ML:** scikit-learn, LightGBM, optional XGBoost and small neural networks.
- **Optimization:** Deterministic candidate enumeration; optional OR-Tools for portfolio constraints.
- **Testing:** pytest, Docker, k6, optional Prometheus.
- **Infrastructure:** Terraform, Utho provider, GitHub Apps, GitHub Actions.
- **Agent:** MCP tools, an agent orchestration layer, optional Jev/TypeSafe review routing.
- **Emulation:** Floci and LocalStack for selected AWS-compatible control-plane operations.

Redis, PostgreSQL, Kubernetes, GPUs, and a full multi-service OptScale deployment are not prerequisites for the core local architecture. They can be incorporated where the deployment requirements justify them.

### Suggested repository structure

text

```
cloudpilot/
├── frontend/
├── backend/app/
│   ├── api/
│   ├── engine/
│   ├── ml/
│   ├── agent/
│   ├── mcp/
│   ├── adapters/
│   ├── execution/
│   └── models/
├── backend/tests/
├── data/
│   ├── generate_data.py
│   ├── catalog/
│   └── fixtures/
├── experiments/
├── infra/
│   ├── demo-terraform/
│   ├── floci/
│   └── localstack/
├── docs/
├── docker-compose.yml
├── Makefile
└── README.md
```

## 5\. MCP Agent Architecture

The MCP agent is a first-class CloudPilot component. It provides a structured interface through which an AI agent can retrieve infrastructure evidence, invoke optimization services, compare scenarios, explain recommendations, and prepare approved change proposals.

MCP supplies tool interoperability; CloudPilot's backend supplies authorization, policy enforcement, and execution control.

### MCP tool catalogue

**Read-only tools**

- `list_resources`
- `get_metrics`
- `get_candidate_plans`
- `run_optimization`
- `run_risk_assessment`
- `simulate_change`
- `get_alerts`
- `get_cost_breakdown`
- `get_verification_evidence`
- `get_ml_benchmarks`
- `get_dependency_graph`
- `get_recommendation_details`

**Controlled action tools**

- `create_change_proposal`
- `generate_terraform_diff`
- `validate_terraform_plan`
- `open_pr`
- `request_approval`
- `get_change_status`

Action tools enforce authorization and approval requirements in the backend. Tool availability does not itself grant permission to modify infrastructure.

### Agent decision flow

1. Receive a user question or optimization task.
2. Retrieve relevant resource inventory, telemetry, pricing, and dependency information.
3. Call the deterministic optimization engine to generate candidate actions.
4. Request independent policy and risk validation.
5. Compare candidate costs, savings, constraints, and evidence.
6. Explain the recommended action using retrieved evidence.
7. Present the exact proposed change for approval.
8. After authorization, invoke the configured proposal or execution workflow.
9. Retrieve the change status and verification evidence.
10. Record the decision, tool calls, evidence versions, and outcomes.

### Agent boundaries

- The agent does not invent telemetry, provider prices, plan IDs, or benchmark results.
- Hard policy failures cannot be overridden by an LLM.
- Recommendations and explanations remain separate from execution authorization.
- Mutating operations require action-specific, resource-specific approval.
- Every action rechecks evidence freshness, resource ownership, configuration revision, and permissions.
- Tool errors and missing data are surfaced explicitly.

The agent can use deterministic tool calls without an external LLM for reproducible demonstration scenarios. A configured LLM adds conversational planning and explanation capabilities.

## 6\. Data Sources and Public Dataset Research

CloudPilot combines public workload traces, external recommendation examples, algorithm-derived labels, and a reproducible synthetic Utho estate.

### Workload datasets

| Dataset | Intended use |
| --- | --- |
| [Bitbrains GWA-T-12 fastStorage](<https://atlarge-research.com/gwa-t-12/>) | Primary workload time series; approximately 1,250 VMs, with CPU, memory, disk throughput, and network-related metrics |
| [fastStorage archive](<https://atlarge-research.com/gwa-traces/gwa_t_12_fastStorage.zip>) | Raw workload import |
| [Preprocessed Bitbrains CSVs](<https://github.com/alhamedy/Dataset-used-to-build-the-time-series-prediction-models>) | Quick CPU/memory experiments |
| [GWA-T-13 Materna](<https://atlarge-research.com/gwa-t-13/>) | Additional workload validation |
| [Bitbrains Rnd](<https://atlarge-research.com/gwa-traces/gwa_t_12_rnd.zip>) | Complementary workload patterns |
| [Azure Public Dataset V1](<https://github.com/Azure/AzurePublicDataset/blob/master/AzurePublicDatasetV1.md>) | Selected CPU trace analysis; process relevant subsets instead of loading the full archive |
| [Azure VM Noise 2024](<https://github.com/Azure/AzurePublicDataset/blob/master/AzureVMNoiseDataset2024.md>) | Performance variability research |
| Alibaba Cluster Trace 2017 | Scheduling and workload stress tests |
| [Google Cluster CPU subset](<https://zenodo.org/records/6979672>) | Lightweight forecasting sanity checks |

Bitbrains disk throughput is not equivalent to disk capacity utilization or IOPS. Those fields are separately sourced or synthesized and labelled accordingly.

### Recommendation and supervised-learning datasets

| Source | Intended use |
| --- | --- |
| [Synthetic Cloud Optimization Recommendations](<https://huggingface.co/datasets/ameau01/synthesized-cloud-optimization-recommendations>) | Schema examples and separate agent evaluation; 18 examples are useful for scenario testing |
| [Multi-Cloud Resource Dataset](<https://www.kaggle.com/datasets/freshersstaff/multi-cloud-resource-dataset>) | Initial classification experiments for scale-up, scale-down, and no-action |
| [Example XGBoost project](<https://github.com/dhanushmb/Intelligent-Cloud-Cost-Optimization-Forecasting-System-/>) | Reference CSV structure and classifier implementation |
| [AWS Compute Optimizer exports](<https://docs.aws.amazon.com/compute-optimizer/latest/ug/exporting-recommendations.html>) | Potential future teacher labels from authorized accounts |
| [Microsoft Lorentz research](<https://www.microsoft.com/en-us/research/publication/lorentz-learned-sku-recommendation-using-profile-data/>) | Learned SKU allocation methodology |

Dataset labels and plan names are validated before use. Algorithm-generated labels are explicitly identified as synthetic or teacher-policy-derived, not as proven production-optimal decisions.

### Synthetic Utho estate

Generate 120 VMs × 30 days × 96 fifteen-minute observations per day, totalling **345,600 VM observations**.

Include:

- Three regions and three environments.
- Resource owners, teams, criticality, creation dates, and plan identifiers.
- Compute, memory, disk, IOPS, and network attributes.
- Volumes, unattached storage, public IPs, and six-month billing snapshots.
- Terraform-managed, unmanaged, and unknown-management resources.
- Resource dependency relationships.
- Steady-low, bursty, batch, weekday-only, memory-bound, and network-bound workloads.
- Anomalies, cost spikes, orphaned resources, and insufficient-data cases.

Use deterministic random seeds, compact CSV/Parquet fixtures, versioned prices, and explicit provenance labels.

## 7\. ML Forecasting and Supervised Recommendation Models

The ML engine predicts future workload demand. A separate constrained optimizer selects a valid provider plan.

### Features and targets

Features include allocated vCPU and RAM, current utilization, rolling peaks, p95/p99, temporal lags, cyclical time features, missingness, criticality, dependencies, and forecast horizon.

Targets include maximum CPU demand, maximum memory demand, and selected throughput metrics over the next hour or day.

### Model comparison

- Historical rolling-p99 and seasonal-naive baselines.
- Ridge regression.
- Random Forest.
- LightGBM quantile regression.
- Optional XGBoost.
- Optional small MLP, LSTM, or Transformer experiments.

Training is CPU-based, with capped parallelism and controlled dataset sizes.

### Evaluation

Use chronological training, validation, and test windows, with a purge gap for overlapping targets and a separate VM holdout test.

Evaluate:

- Pinball loss and quantile coverage.
- Peak underprediction rate.
- Capacity and SLO constraint violations.
- Cost of selected configurations.
- Regret against the simulated future-optimal plan.
- Inference runtime and memory consumption.

A model that performs worse than the baseline is still evaluated and documented; the selection policy uses the stronger validated method.

### Teacher labels

Generate reference labels by evaluating valid plans against future workload replay and constraints. Supported actions include `upsize`, `downsize`, `schedule`, `no_action`, `review_orphan`, and `defer_insufficient_data`.

Classical supervised learning on these labels is distinct from LLM supervised fine-tuning. The latter uses curated decision/explanation examples and is an additional model-training path.

## 8\. Constrained Optimization and Cost Economics

For each resource, enumerate valid plans and minimize projected cost while satisfying capacity, compatibility, and workload constraints.

The objective incorporates monthly infrastructure cost, modeled risk, and migration cost. Portfolio optimization can additionally account for budgets, dependencies, and change conflicts.

### Supported actions

- Resize to a valid existing plan.
- Schedule non-production stop/start.
- Investigate idle resources.
- Review orphaned volumes and IP addresses.
- Analyze storage and network optimization opportunities.
- Recommend no action or defer when evidence is insufficient.

### Validation dimensions

- CPU high quantiles and short-duration peaks.
- Physical memory requirements.
- Disk capacity and growth.
- Disk IOPS and network bandwidth.
- Region-specific plan availability.
- Architecture, licensing, and family compatibility.
- Resource dependencies and criticality.
- Telemetry freshness and coverage.
- Billing type and minimum charges.
- Scheduled jobs, health checks, and rollback procedures.

### Cost calculations

Maintain versioned provider prices and separate compute, storage, IP, backup, and egress charges.

Calculate projected monthly savings with one-time costs shown separately. Apply actual billing rules for stopped instances and minimum commitments. Reconcile overlapping resize and scheduling actions to prevent double-counting.

The UI distinguishes accepted portfolio savings from potential savings awaiting approval.

## 9\. Safety Validation and Verified Savings

CloudPilot combines deterministic policy checks, probabilistic scenario analysis, and measured application benchmarking.

### Hard policy checks

Validate data freshness, plan compatibility, memory/storage/IOPS/network capacity, disk shrink restrictions, production scheduling policies, Terraform drift, application health, and ownership approval.

Hard failures block execution proposals.

### Scenario analysis

Replay historical workloads using time-block resampling to preserve daily and weekly patterns. Evaluate two-times launch traffic, month-end batch loads, memory spikes, and network stress.

Report the observed fraction of simulated scenarios that breach constraints as **modeled breach frequency**, not actual outage probability.

### Application benchmark

Run a sample API using Docker resource limits and generate traffic with k6. Measure p95 latency, HTTP error percentage, CPU throttling, out-of-memory events, and restarts for baseline and candidate configurations.

Optionally use Prometheus to collect metrics.

Docker results are measurements of the tested container environment, not proof of identical performance on Utho hardware.

### Evidence packet

Each recommendation exports:

- Input metrics and provenance.
- Forecasts and model version.
- Current and candidate plan details.
- Pricing and cost calculations.
- Passed, failed, and uncertain safety checks.
- Scenario outcomes.
- Benchmark provenance.
- Required approvals.
- Rollback procedure and verification status.

## 10\. Jev and TypeSafe Integration

Jev and TypeSafe are included as an optional typed decision and contextual review layer.

Potential uses include:

- Routing routine recommendations for standard review.
- Escalating production or high-impact changes to senior SRE review.
- Requesting more information when telemetry or ownership is incomplete.
- Ranking explanations and organizing review evidence.

Jev-derived probabilities are not treated as calibrated outage probabilities. Its decisions cannot override deterministic safety gates or authorization rules.

The core optimizer, safety validator, and local demo remain functional when the integration is not configured.

## 11\. Floci, LocalStack, Docker, and Prometheus

### Floci

[Floci](<https://github.com/floci-io/floci>) provides an AWS-shaped control-plane emulation option for testing selected API interactions, resource discovery, and mock lifecycle workflows.

### LocalStack

[LocalStack](<https://github.com/localstack/localstack>) provides an alternative AWS-compatible local testing environment. Its supported services, licensing, and features are checked against the required tests.

### Integration strategy

Use Floci as the primary AWS-compatible emulator candidate and LocalStack as an alternative. Run whichever provides the required reproducible API coverage without making both mandatory.

Both are used for AWS-compatible API behavior, not as native Utho emulators or performance simulators.

### Docker and k6

Docker and k6 independently validate application behavior under controlled CPU and memory limits. Optional Prometheus integration collects measured metrics.

This separates control-plane integration testing from workload-performance experiments.

## 12\. Utho Provider and Terraform Integration

Reference provider:

[Utho Terraform provider](<https://github.com/uthoplatforms/terraform-provider-utho>)

Relevant resources:

- `utho_cloud`
- `utho_cloud_resize`
- `utho_cloud_power`
- `utho_cloud_snapshot`
- Provider plan data sources, including `cloud_plans`.

The integration inspects plan replacement behavior, dedicated resize operations, shutdown requirements, `ramcpu` versus `full` resize modes, data-center plan availability, and storage limitations before proposing a change.

Provider behavior is tested in a reproducible demo environment before any executable workflow is enabled.

### Three execution modes

**GitOps-managed resources**

1. Customer authorizes a GitHub App or customer-owned connector.
2. CloudPilot generates an exact infrastructure diff.
3. A branch and pull request are created.
4. CI runs Terraform validation, policy checks, and a plan.
5. The authorized customer workflow reviews and applies the change.
6. CloudPilot verifies the outcome and records the evidence.

**Unmanaged resources**

A scoped provider adapter prepares approved API operations. Resource ownership, action-bound authorization, permissions, idempotency, and last-minute configuration checks are required.

**Manual execution**

CloudPilot generates runbooks, commands, Terraform snippets, prerequisites, verification steps, and rollback instructions.

### Security controls

- No unrestricted shell execution by the agent.
- No model-owned secrets.
- No blanket infrastructure permissions.
- Approval bound to the exact resource, action, configuration, and evidence version.
- Expiring authorization, audit logging, idempotency, and drift/revision checks.
- Customer-controlled apply permissions.
- A future customer-hosted outbound executor for enterprise deployments.

## 13\. Existing Market and Open-Source Benchmark

| Project | Existing capabilities | CloudPilot differentiation |
| --- | --- | --- |
| [Hystax OptScale](<https://github.com/hystax/optscale>) | Multi-cloud cost analysis, rightsizing, schedules, budgets | Evidence-backed replay and controlled infrastructure proposals |
| [Robusta KRR](<https://github.com/robusta-dev/krr>) | Kubernetes percentile rightsizing | VM plans, cloud costs, and approval workflows |
| [CAST AI](<https://cast.ai/>) | Cloud and Kubernetes optimization | Transparent workload validation and evidence packets |
| [Kubecost](<https://www.kubecost.com/>) / [OpenCost](<https://www.opencost.io/>) | Kubernetes cost allocation | VM, storage, IP, and provider-plan optimization |
| [Infracost](<https://www.infracost.io/>) | Terraform cost diffs | Usage-driven optimization before infrastructure changes |

### OptScale implementation references

- Instance rightsizing: percentile-driven rightsizing and candidate flavour selection.
- Rightsizing base logic: approximate CPU requirements, plan matching, and cost comparison.
- Shutdown recommendations: inactivity windows and shutdown economics.

These references inform a focused CloudPilot implementation. The full OptScale deployment is not required.

## 14\. Fifteen Additional Product Ideas

All fifteen ideas are retained in the product design.

| # | Feature | Implementation |
| --- | --- | --- |
| 1 | SLO-aware optimization | Reject configurations violating latency or error constraints |
| 2 | Counterfactual replay | Compare daily bursts across alternative vCPU configurations |
| 3 | Savings confidence intervals | Calculate plausible savings ranges under explicit assumptions |
| 4 | Portfolio Pareto frontier | Compare conservative, balanced, and aggressive cost-risk outcomes |
| 5 | Shadow mode | Replay historical decisions without infrastructure mutations |
| 6 | Rollback triggers | Define failure thresholds and rollback-ready procedures |
| 7 | Change-conflict detection | Detect stale approvals and incompatible Terraform revisions |
| 8 | Dependency blast-radius graph | Identify downstream services affected by proposed changes |
| 9 | Per-environment risk budgets | Apply production, staging, and development policies |
| 10 | Capacity stress scenarios | Simulate future growth, traffic spikes, and batch loads |
| 11 | Feedback learning | Compare predicted savings against observed outcomes |
| 12 | Inferred owners | Suggest owners of untagged resources for human verification |
| 13 | Data-quality abstention | Defer recommendations when evidence is insufficient |
| 14 | Unit economics | Calculate cost per customer, request, or transaction |
| 15 | Topology/network optimization | Evaluate egress, regional placement, IP, and network trade-offs |

These capabilities use shared resource models, dependency graphs, pricing, simulation, and evidence services.

## 15\. REST API and Data Contracts

### Core API

text

```
GET    /api/health
GET    /api/summary
GET    /api/resources?region=&environment=&team=&type=
GET    /api/resources/{resource_id}/metrics?start=&end=
GET    /api/plans?region=
GET    /api/recommendations?risk=&status=
GET    /api/recommendations/{id}
PATCH  /api/recommendations/{id}
POST   /api/simulate
POST   /api/verify
GET    /api/alerts
GET    /api/ml/benchmarks
POST   /api/changes/propose
GET    /api/changes/{id}
```

### Agent and MCP services

The agent uses the same typed backend services for inventory, metrics, plan discovery, optimization, risk assessment, simulation, evidence retrieval, and controlled change proposals.

This ensures the UI and MCP agent share a consistent source of truth.

### Recommendation record

Each recommendation stores:

- Recommendation and resource IDs.
- Observation window and feature version.
- Model and catalogue versions.
- Current and proposed plans.
- Action type and cost before/after.
- Estimated savings and assumptions.
- Risk class and hard-gate results.
- Scenario breach frequency.
- Verification results and provenance.
- Status, approver, and approval timestamp.
- Terraform revision and pull request URL, when available.

### Lifecycle

`DETECTED → ANALYZED → VERIFIED → PROPOSED → APPROVED → PR_OPEN / DRY_RUN → APPLIED → MONITORED`

Additional states include `REJECTED`, `BLOCKED`, `INSUFFICIENT_DATA`, `FAILED`, and `ROLLED_BACK`.

Simulated states and live infrastructure states remain distinguishable.

## 16\. Testing and Acceptance Criteria

### Functional tests

1. Generate 120 VMs and exactly 30 days of fifteen-minute telemetry.
2. Generate anomalies, orphaned resources, billing snapshots, and realistic resource metadata.
3. Run the application locally without cloud credentials.
4. Verify filters, graphs, recommendation actions, simulation, and alerts.
5. Validate candidate plans against regional availability and compatibility constraints.
6. Block unsafe peak-demand and memory-bound downsizing.
7. Defer recommendations with insufficient data.
8. Require ownership verification for orphan cleanup.
9. Verify non-production schedule previews and billing assumptions.
10. Prevent savings double-counting across overlapping actions.
11. Compare historical baselines, Ridge, and LightGBM on chronological test data.
12. Record forecast coverage, unsafe-candidate rate, runtime, and simulated savings.
13. Measure actual Docker/k6 p95 latency and HTTP errors.
14. Test selected Floci, LocalStack, or reproducible API-mock operations.
15. Generate a validated Terraform diff and dry-run result.
16. Test MCP tool permissions, approval binding, audit records, and failure handling.
17. Verify that unauthorized infrastructure mutations cannot be executed.
18. Run backend pytest tests and the frontend production build.

### Quality and handoff

- Windows PowerShell setup instructions.
- Optional Docker Compose setup.
- Sample configuration and `.env.example`.
- Deterministic seed data and repeatable training scripts.
- Dataset provenance and attribution.
- Pricing and assumptions sheet.
- Architecture and safety documentation.
- Evidence packet and demo scenarios.
- Five- to seven-minute presentation.
- Fallback demo recording.

## 17\. Implementation Schedule

| Time | Work |
| --- | --- |
| Hours 0–4 | Project skeleton, data schemas, API contracts, frontend routes |
| Hours 4–12 | Synthetic estate, catalogue, deterministic optimizer, dashboard |
| Hours 12–20 | Forecasting experiments, candidate search, risk gates, savings |
| Hours 20–28 | Replay, Docker/k6, MCP integration, approval and Terraform proposal |
| Hours 28–34 | UI/API integration, alerts, evidence, audit, emulator tests |
| Hours 34–42 | Acceptance testing, integration checks, documentation, demo |

### Team responsibilities

- **Contributor 1:** Backend, optimization, cost engine, APIs.
- **Contributor 2:** Frontend, dashboards, simulator, user experience.
- **Contributor 3:** Dataset pipeline, ML, model evaluation, scenario generation.
- **Contributor 4:** MCP agent, infrastructure integrations, Terraform, testing, and demonstration.

Shared interfaces are agreed early so the components can be developed in parallel.

## 18\. Resource Library

### Official brief, pricing, and infrastructure

- Utho problem statement: `TF'26 PROBLEM STATEMENTS.pdf`, pages 44–47.
- [Utho pricing](<https://utho.com/pricing>)
- [Utho Terraform provider](<https://github.com/uthoplatforms/terraform-provider-utho>)
- [Terraform documentation](<https://developer.hashicorp.com/terraform/docs>)
- [OpenTofu documentation](<https://opentofu.org/docs/>)
- [GitHub Apps](<https://docs.github.com/en/apps>)
- [GitHub Actions](<https://docs.github.com/en/actions>)
- [Model Context Protocol](<https://modelcontextprotocol.io/>)

### Datasets and ML

- [Bitbrains GWA-T-12](<https://atlarge-research.com/gwa-t-12/>)
- [Bitbrains fastStorage](<https://atlarge-research.com/gwa-traces/gwa_t_12_fastStorage.zip>)
- [Bitbrains Rnd](<https://atlarge-research.com/gwa-traces/gwa_t_12_rnd.zip>)
- [Materna](<https://atlarge-research.com/gwa-t-13/>)
- [Preprocessed Bitbrains](<https://github.com/alhamedy/Dataset-used-to-build-the-time-series-prediction-models>)
- [Azure Public Dataset](<https://github.com/Azure/AzurePublicDataset/blob/master/AzurePublicDatasetV1.md>)
- [Azure VM Noise](<https://github.com/Azure/AzurePublicDataset/blob/master/AzureVMNoiseDataset2024.md>)
- Alibaba Cluster Trace
- [Google CPU subset](<https://zenodo.org/records/6979672>)
- [Synthetic optimization examples](<https://huggingface.co/datasets/ameau01/synthesized-cloud-optimization-recommendations>)
- [Multi-cloud resource dataset](<https://www.kaggle.com/datasets/freshersstaff/multi-cloud-resource-dataset>)
- [Example XGBoost project](<https://github.com/dhanushmb/Intelligent-Cloud-Cost-Optimization-Forecasting-System-/>)
- [AWS Compute Optimizer](<https://docs.aws.amazon.com/compute-optimizer/latest/ug/exporting-recommendations.html>)
- [Microsoft Lorentz research](<https://www.microsoft.com/en-us/research/publication/lorentz-learned-sku-recommendation-using-profile-data/>)

### Optimization and cost benchmarks

- [OptScale](<https://github.com/hystax/optscale>)
- [Robusta KRR](<https://github.com/robusta-dev/krr>)
- [CAST AI](<https://cast.ai/>)
- [Kubecost](<https://www.kubecost.com/>)
- [OpenCost](<https://www.opencost.io/>)
- [Infracost](<https://www.infracost.io/>)

### Emulation, testing, and AI

- [Floci](<https://github.com/floci-io/floci>)
- [LocalStack](<https://github.com/localstack/localstack>)
- [LocalStack licensing](<https://docs.localstack.cloud/aws/licensing/>)
- [Docker](<https://docs.docker.com/>)
- [k6](<https://grafana.com/docs/k6/latest/>)
- [Prometheus](<https://prometheus.io/docs/>)
- [Jev](<https://jevaihub.com/>)
- [TypeSafe AI](<https://typesafe.ai/>)
- [FastAPI](<https://fastapi.tiangolo.com/>)
- [LightGBM](<https://lightgbm.readthedocs.io/>)
- [DuckDB](<https://duckdb.org/docs/>)

## 19\. Research and Integration Validation

Implementation includes verification of current provider prices, resize semantics, supported plan IDs, storage limitations, GitHub authorization, emulator coverage, dataset licences, and ML performance.

Where a provider, external service, or dataset requires credentials, configuration, or additional setup, the corresponding adapter and test workflow are included in the architecture.

Measured outcomes are generated by experiments. Simulated outcomes are labelled as simulated. External integrations are tested against their documented and observed capabilities.

## 20\. Final Product Definition

CloudPilot integrates FinOps analytics, forecasting, constrained optimization, MCP-based AI assistance, cloud emulation, workload verification, Terraform/GitOps automation, and evidence-backed approval workflows.

Its defining feature is **Verified Savings**: every optimization recommendation connects the proposed action to its cost impact, workload evidence, safety analysis, approval requirements, execution path, and verification results.

The deliverable is a modular, extensible platform whose local prototype demonstrates the complete decision workflow and whose integration interfaces support expansion to configured cloud environments.

**One-line pitch:** CloudPilot doesn't just identify cloud waste. It predicts demand, selects a valid lower-cost configuration, validates workload risk, explains the decision through an MCP-enabled agent, and prepares the approved change for controlled execution.

This version restores the MCP agent and the supporting research and infrastructure ideas, while keeping the full product scope in one specification.

I can next create a feature-by-feature implementation checklist mapped to the exact files, MCP tools, APIs, and tests so the team can build directly from this document.