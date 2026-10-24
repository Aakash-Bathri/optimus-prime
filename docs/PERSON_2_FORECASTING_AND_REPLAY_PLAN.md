# Person 2 — Demand Forecasting and Capacity Evidence

Detailed implementation plan for the CloudPilot optimization recommendation engine.

Status: proposed implementation, not completed functionality. Assignment source: `../5people.md`, Person 2. Read alongside `PERSON_3_OPTIMIZATION_ENGINE_PLAN.md`.

## 1. Outcome and ownership

Build the demand-analysis service that answers: **What capacity does this workload appear to need, what happens on a proposed plan, and how strong is the evidence?**

Own `backend/app/ml/`, `experiments/`, features, deterministic forecasts, optional model experiments, historical replay, stress scenarios, and versioned evidence. Person 3 owns candidate enumeration, policy thresholds, final recommendations, prices, and approval enforcement. You provide measurements and estimates; you do not choose a billable plan or authorize a change.

The engine must work with deterministic statistical estimates before any ML training succeeds. ML experiments are an enhancement, not a dependency of core recommendations.

## 2. Scope and sequencing

| Priority | Deliverable | Completion condition |
| --- | --- | --- |
| P0 | Contracts and fixtures | Person 3 can call forecast/replay functions using fixture inputs |
| P0 | Quality checks and demand features | Invalid, stale, sparse, or incompatible data yields explicit outcomes |
| P0 | Rolling-p99 and seasonal baselines | Repeated runs produce the same outputs |
| P0 | Historical candidate replay | CPU and memory breaches are visible per candidate |
| P0 | Stress scenarios and evidence | Assumptions and failed/unknown checks are returned |
| P1 | Chronological model evaluation | Baselines, Ridge, and optional LightGBM are compared fairly |
| P1 | Selected-model artifact | Selection follows measured validation performance |
| P2 | Public-trace evaluation | Only after core integration; preserve source semantics and attribution |

Keep the 40–42-hour handoff schedule from the assignment as a planning envelope. If the competition build uses the shorter one-day scope in `PRODUCT_DEFINITION.md`, retain P0 and defer P1/P2. Use Person 1's delivered manifest for estate size; do not duplicate conflicting 100/120-VM assumptions in code.

## 3. Module layout

```text
backend/app/ml/
  contracts.py           # Typed requests, results, quality, evidence
  quality.py             # Coveraage, freshness, continuity, validity
  features.py            # Absolute demand, quantiles, time features
  baselines.py           # Rolling-p99 and seasonal-naive estimates
  forecasting.py         # Method selection and callable service
  replay.py              # Historical capacity projection
  scenarios.py           # Deterministic stress transforms/block samples
  artifacts.py           # Versioned model and evidence metadata
experiments/
  README.md              # Reproduction and limitations
  config/                # Frozen split, seed, features, experiment limits
  run_benchmarks.py       # Proposed experiment entry point
  results/               # Machine-readable metrics and readable summary
```

These are proposed paths. Keep data access behind a small repository/adapter interface so the service can use Person 1's delivered storage format without owning ingestion.

## 4. Freeze the input contract first

Agree with Persons 1 and 3 on:

- Stable resource ID and configuration revision; interval length and UTC timestamps.
- CPU percent meaning: percentage of total allocated vCPU, not percent of one core.
- Memory percent denominator, capacity units, and whether values describe used or working-set memory.
- Timestamped capacity or configuration history. Split a series at resize boundaries; never apply today's capacity to historical percentages from a different plan.
- Metric units: cores, GiB, disk GiB, IOPS, and network Mbps. Convert bits/bytes explicitly. Unsupported units cause an error or unknown result.
- Dataset version, provenance, observation interval, expected samples, missing samples, and ingestion time.
- Plan capabilities supplied by Person 3; unknown network/IOPS capacity remains unknown.

Use half-open windows `[start, end)` throughout. Duplicate timestamps, invalid negative demand, and values outside declared metric semantics are reported, not silently repaired. Preserve a missingness mask when resampling.

## 5. Shared callable interface

```python
forecast(request: ForecastRequest) -> ForecastResult
replay(request: ReplayRequest) -> ReplayResult
evaluate_scenarios(request: ScenarioRequest) -> ScenarioResult
get_benchmarks() -> BenchmarkReport
```

`ForecastRequest` includes resource ID, configuration revision, cutoff time, observation window, horizon, interval, dataset version, and policy version. Default proposed horizon: 24 hours in 15-minute steps; keep it configurable.

`ForecastResult` includes:

| Field | Meaning |
| --- | --- |
| `status` | `ok`, `insufficient_data`, or `unsupported` |
| `resource_id`, `configuration_revision` | Identity to prevent evidence reuse after a change |
| `cutoff`, `observation_window`, `horizon` | Explicit temporal scope |
| `cpu`, `memory` | Absolute-demand estimates; optional time series |
| `uncertainty` | Quantiles/intervals where validated, otherwise unavailable |
| `quality` | Expected/valid samples, coverage, freshness, gaps |
| `method`, `method_version`, `feature_version` | Reproducible method identity |
| `dataset_version`, `evidence_id`, `generated_at` | Evidence provenance |
| `warnings`, `assumptions` | Limitations and missing dimensions |

Do not call a rolling p99 an automatically calibrated 99% forecast interval. Label it a historical demand estimate. Ridge produces a point estimate unless a separate uncertainty method is evaluated.

`ReplayRequest` includes the same resource/window/version identity, candidate plan ID and capacity, policy thresholds, and scenario parameters. `ReplayResult` returns evaluated/unknown dimensions, sample count, breach counts/fractions, longest consecutive breach, peak projected utilization, failed constraints, and assumptions. Return per-dimension results and the union of breached timestamps; do not sum overlapping CPU and memory counts.

Provide JSON fixtures for success, insufficient data, unsafe CPU, unsafe memory, and unknown network capacity before building models. Person 3 owns REST serialization and HTTP errors.

## 6. Data-quality rules

Put thresholds in shared versioned policy, owned by Person 3. Proposed starting values for review:

| Rule | Proposed default | Behavior |
| --- | --- | --- |
| Recent data | Latest sample within two intervals | Otherwise abstain from sizing |
| Coverage | At least 95% valid CPU and memory observations | Otherwise insufficient data |
| History | At least 7 days for rolling baseline | Otherwise insufficient data |
| Seasonal history | At least two complete weeks | Otherwise use rolling baseline with warning |
| Continuous gap | No gap exceeding 2 hours | Otherwise insufficient data |

These values are demo design choices, not production guarantees. Count expected observations from the requested interval, not from the first and last surviving sample. Check coverage by day and proposed off-hour window as well as overall coverage: a systematically missing batch window cannot pass because total coverage is high. Do not fill missing demand with zero.

## 7. Demand features

For each observation with known configuration:

```text
used_cpu_cores = cpu_percent / 100 * allocated_vcpu
used_memory_gib = memory_percent / 100 * allocated_memory_gib
```

Compute p95, p99, observed maximum, rolling mean/max/quantiles, daily maxima, weekday/weekend summaries, and recurring peak windows. Retain maximums separately so a low percentile does not hide a brief burst. Add time-of-day/day-of-week features, lags at one interval/one day/one week, and missingness flags for optional models.

All input features at origin `t` use timestamps strictly before the forecast target interval. Fit scalers, imputers, and encoders on training data only. Distinguish observed utilization from latent demand: a VM pinned at 100% may have unmet demand that telemetry cannot quantify. Flag saturation and prohibit evidence claiming unconstrained demand is known.

## 8. Deterministic baselines

1. **Rolling-p99:** estimate CPU and memory from the trailing valid window; also return observed peaks. This is a capacity summary baseline, even when repeated across a horizon.
2. **Seasonal naive:** use the matching slot from the prior week for each future interval; document the behavior if that slot is absent. Fall back to rolling baseline only when its own data-quality requirements pass.
3. Person 3 combines forecast demand with historical p99, peaks, and headroom. A low model forecast never erases a historical peak check.

Start with these methods integrated end to end. Forecast errors must not silently become a zero-demand response.

## 9. Optional model experiment, capped at approximately five hours

Use a bounded VM subset and fixed seed; record its IDs and workload types. Cap CPU workers and memory. Compare identical forecast targets across rolling baseline, seasonal baseline, Ridge, and LightGBM quantile models if installation/time permits. Defer Random Forest and neural models.

Use interval-level CPU demand targets for the next-day horizon. If training a window-maximum model instead, declare that target separately and compare baselines transformed to the same target. Do not compare an interval forecast with a daily maximum as though their losses were interchangeable. Evaluate memory separately or retain a conservative memory baseline.

Proposed 30-day split: training days 1–18, validation days 20–24, test days 26–30, leaving days 19 and 25 as a 24-hour boundary gap for a 24-hour target. Form training origins only when their entire target window ends inside the training period. Recalculate purge boundaries if the target horizon changes.

Reserve an explicit VM holdout before training. Use validation VMs/windows for hyperparameters and method selection; run the frozen choice once on untouched temporal test and VM-holdout data. A global model may use prior history of a held-out VM at inference but must not train on its targets. Document how much history is available.

Report:

- MAE for point forecasts; pinball loss for actual quantile predictions.
- Empirical quantile coverage and interval width where applicable.
- Peak underprediction rate, with a fixed documented peak definition and tolerance.
- Sample counts and results by workload class, not only a global average.
- Training time, inference time, peak memory, environment and dependency versions.
- Unsafe-candidate rate and modeled cost using Person 3's identical frozen optimizer and policy on each method.

Choose using validation results: first satisfy the agreed underprediction/capacity criterion, then compare loss and runtime. If no learned method improves the baseline under those criteria, ship the baseline. Never tune against final test results. Any future-aware cheapest-plan oracle is a simulated retrospective reference, not a deployable policy or proof of optimal production savings.

## 10. Historical replay

For every valid observation, project absolute demand onto candidate capacity:

```text
projected_cpu_fraction = used_cpu_cores / candidate_vcpu
projected_memory_fraction = used_memory_gib / candidate_memory_gib
breach = projected_fraction > policy_limit
breach_frequency = breached_evaluable_intervals / evaluable_intervals
```

Use shared policy thresholds, not independently selected ML thresholds. Report both policy-limit breaches and physical-capacity breaches. Preserve the original timestamp order to report longest consecutive breach. An eight-core VM using 3.2 cores maps to 160% on two cores and 80% on four cores; under an 80% CPU policy limit the former fails and the latter is at the boundary, subject to every other check.

CPU scaling assumes comparable architecture/family and approximately linear capacity. This is modeled evidence; it does not predict latency or prove an SLO. Memory demand is not reduced simply because CPU is reduced. Evaluate disk/IOPS/network only when both demand and compatible capacity semantics exist.

## 11. Stress scenarios

Implement direct deterministic transforms first:

| Scenario | Transform | Required disclosure |
| --- | --- | --- |
| Traffic growth | CPU/network demand × configured factor, e.g. 1.5 or 2 | Memory remains separate unless a memory model is declared |
| Batch load | Add demand within a declared recurring time window | Window, duration, added demand and timezone |
| Memory spike | Multiply/add memory for a declared duration | Factor/addition and overlap with existing peaks |
| Network stress | Multiply network demand | Unknown if throughput/capacity units cannot be compared |

For optional resampling, draw contiguous daily blocks with a fixed seed, retaining intraday order and all metrics together. Match weekday/weekend blocks; use whole-week blocks when weekly patterns matter and history permits. Never independently shuffle CPU and memory. Return seed, block length, sample count, scenarios, parameters and exact denominator. Replayed/sampled breach frequency is modeled evidence, not outage probability. Bootstrap intervals, if supplied, describe this sampling procedure only.

## 12. Handoffs and implementation order

| Time | Work | Handoff |
| --- | --- | --- |
| Hours 0–4 | Contracts, units, quality semantics, fixture responses | Persons 1, 3, 4, 5 |
| Hours 4–8 | Feature extraction and rolling baseline | Person 3 integrates callable service |
| Hours 8–12 | Seasonal baseline, quality outcomes, historical replay | Working baseline recommendation journey |
| Hours 12–20 | Five-hour experiment budget, result report, selected artifact | Persons 3 and 4 |
| Hours 20–28 | Stress scenarios, frozen demo evidence, integration fixes | Persons 3 and 5 |
| Hours 28 onward | Reproduction, acceptance, documentation | No new model families |

If data is late, develop against agreed small fixtures. If model work overruns, freeze the baseline. If a dependency cannot be installed, record the skipped experiment; do not invent measurements.

## 13. Required behavioral checks

| Case | Expected result |
| --- | --- |
| Missing all memory samples | Sizing abstains; CPU-only output cannot claim full validation |
| Missing batch window | Quality fails even if global coverage is superficially high |
| Historical configuration change | Correct timestamped denominator or explicit unsupported result |
| Short CPU burst | Peak retained and aggressive candidate fails |
| Memory-bound workload | CPU-light candidate still fails memory |
| Saturated current resource | Latent demand warning; no confident downsize |
| Future observations added beyond cutoff | Earlier-origin features and forecast stay unchanged |
| Repeated seed/input/version | Identical replay/scenario output |
| Unknown network limit | Unknown check, never a pass |
| Failed model load | Explicit baseline fallback with method/version and warning |

## 14. Definition of done

- Person 3 can call stable functions with no training step or external credentials.
- Valid data produces absolute-demand evidence; insufficient data produces abstention.
- Peaks, memory, gaps, saturation, and configuration history are handled explicitly.
- Candidate and scenario evidence identifies failed and unknown constraints.
- Selected methods have reproducible evaluation; unrun experiments are labeled unrun.
- Evidence binds resource, configuration, data, method, policy and time window.
- README supplies exact working commands after implementation and a compact measured results table.

First commit: contracts plus fixtures. Second: quality/features/baselines. Third: replay/scenarios. Fourth: experiments and measured selection only if core integration is complete.
