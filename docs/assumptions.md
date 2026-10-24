# Implemented assumptions and policy

This sheet describes the first working increment, not verified Utho behavior.
The reference is `CloudPilot_Algorithms_and_Models.md`; source facts come from
`test-data/assumptions.json` and the delivered CSVs.

## Sources and units

- 200 synthetic resources: 150 VMs, 20 block volumes, 20 public IPs, 10 GPUs.
- 30 days, 15-minute interval: `[2026-09-15T00:00:00Z, 2026-10-15T00:00:00Z)`.
  Source timestamps are naive. **UTC is an explicit, unverified interpretation.**
  No source timezone has been established for live scheduling decisions.
- CPU is a percentage of allocated vCPUs; RAM is a percentage of allocated memory.
  Absolute CPU cores and RAM GiB are recomputed from inventory capacity. The
  manifest describes RAM as GiB; disk capacity retains source GB units. Network
  is Mbps; disk activity is IOPS, not a latency or throughput measurement.
- Current capacity is assumed constant through the synthetic observation window.
  No configuration history is supplied. This adapter is not suitable for a live
  dataset with unresolved resize history.
- Complete CPU, RAM, disk, IOPS, inbound and outbound observations are required for
  coverage. Missing and invalid numbers become absent observations, never zero.
  Duplicate resource/timestamp pairs, off-grid samples, bad references and
  inventory/catalog/price inconsistencies fail import atomically.
- The supplied event file contains 10 exact duplicate GPU inventory rows. Identical
  IDs/content are counted once and reported; conflicting content with the same ID
  fails import. Original files are never modified.
- Source events are displayed as context. Names, profile counts, expected outcomes
  and event descriptions do not determine recommendations or alerts. The manifest
  mentions oracle/label files that are absent; neither is required or consumed.

## Billing

- Currency: INR. Compute comparison: exact quarterly price divided by three,
  rounded to two decimal places with ROUND_HALF_UP. Published hourly precision is
  preserved separately. This is a commitment monthly equivalent, not a provider
  monthly tariff, a calendar-month hourly bill or immediately realizable cash.
- Block storage uses the source per-GB monthly amounts. A separately inventoried
  volume is counted once, even when linked from VM detail. VM resize does not
  remove storage, an IP or an accelerator.
- Stop/start schedules do not reduce billed compute in this snapshot. Stop-only
  cash savings are zero. No generic `hourly price × stopped hours` formula is used.
- Public-IP and GPU tariffs are unknown; all 30 affected resources retain null
  costs. Known-cost totals are partial. Unknown tariffs never become zero.
- GST, discounts, interruption/migration charges and account commitments have not
  been verified. Catalog region availability and prices have not been independently
  verified. Conditional differences are comparative estimates, not net savings.
- Six billing months (April–September 2026) are generated scenarios, not invoices.
  Billing reconciliation and verified post-change savings are unavailable.

## Versioned sizing policy

Implementation: `backend/app/engine/policy.py`, version `conservative-demo-v1`.

| Rule | Value |
| --- | --- |
| CPU peak / memory peak | At most 80% of target capacity |
| Disk occupancy | At most 80%; no disk shrinking |
| Complete telemetry coverage | At least 95% |
| Minimum history | 7 days |
| Latest complete sample | Within 3,600 seconds of the historical cutoff |
| Stress scenario | Multiply CPU/RAM demand by 1.2; retain the same 80% limits |
| CPU saturation | At least 95% observed usage blocks a confident CPU downsize |
| Idle investigation | Entire-window maxima: CPU ≤5%, RAM ≤20%, IOPS ≤10, combined conservative network peaks ≤1 Mbps |

Boundaries are inclusive. An 80% peak passes that numerical check but can fail the
separate 1.2× stress scenario. All observations, including short spikes, participate
in sizing. p99 and maximum are shown separately. No outlier is removed for savings.
CPU scaling assumes the same hardware/family and linear capacity ratios; this does
not validate per-core performance, latency, concurrency or production SLOs.

All catalog configurations retain their explanations. Unknown regional availability,
price provenance, resize/storage support, IOPS/network capacity or accelerator
compatibility prevent an eligible action. CPU/RAM-feasible alternatives with no
known failed gates can appear as **conditional review candidates**. This distinction
is carried into the UI and exports. Synthetic historical evidence remains a separate
blocking gate even if numerical capacity checks pass.

Historical replay reports observed CPU/RAM-complete sample count, missing count,
per-dimension breaches, their timestamp union, longest consecutive breach run and
stress breaches. A sample violating both CPU and RAM is counted once in the union.
These are modeled threshold breaches, not measured outages or outage probabilities.

## Statistics and alerts

Quantiles use linear interpolation (type 7). EWMA uses alpha 0.1. MAD outliers use
six scaled MADs (1.4826), with no outlier classification when MAD is zero.

Usage alerts compare each observation with the same time of day in the historical
window. Threshold = max(metric floor, 3× slot median, slot median + 6 scaled MADs).
Floors are CPU 40% and IOPS 100. At least seven observations per slot, four hours
of consecutive threshold breaches, and at most 10% exceptional samples are required.
This is a descriptive historical detector without a calibrated false-positive rate.

Capacity alerts use p95 >80% or a peak ≥95%. Data-quality alerts follow the sizing
quality gates. Synthetic cost growth alerts compare the last two billing months at
≥5% increase. Budget is unconfigured: no fabricated budget-overrun alert is issued.
Forecasts and learned models are deferred; no historical quantile is described as
a calibrated prediction interval.

## Review lifecycle and provenance

Pending / accepted / rejected are local planning decisions. **Accepted review-only
items are queued investigations** and have no financial effect. Only an eligible,
financially effective action can change the accepted projection. The current
snapshot has no execution-ready actions. One effective action per resource is
allowed, and each resource's target cost is recomputed once.

Updates bind the full snapshot version and expected decision revision. Decision
and audit writes are transactional; stale changes return 409. Repeating the current
decision with the current revision is idempotent. Dataset-specific IDs prevent old
decisions from silently applying to new evidence; previous audit entries remain.
There is one local engineer persona; authentication/RBAC is not claimed.

Source files, engine/adapter/contracts code and policy participate in the analysis
fingerprint. Exports contain source hashes, implementation hash, catalog/policy
versions, cutoff, unknown charges, blockers, prerequisites and assumptions. Source
changes are picked up at startup, rather than while a request is running. No change
executor, live provider credentials or Docker mutation exists in this increment.
