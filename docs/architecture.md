# Application architecture

The existing local stack is retained: FastAPI + Pydantic, SQLite, React + TypeScript
and Vite/Tailwind. Core recommendation analysis uses Python rules rather than a
trained model. Optional Qwen explanations, a LangChain planner, LocalStack MCP
operations and GitHub PR creation are separate integrations.

At startup, `DatasetSource` hashes and validates the delivered sources. The
repository imports inventory, catalog, indexed telemetry, relationships, events
and billing in one SQLite transaction. Each VM's series is summarized, catalog
candidates are evaluated, replay evidence and alerts are computed, and immutable
results are stored alongside the snapshot metadata. A matching fingerprint reuses
the cache. Failed imports roll back and cannot expose partial results.

`engine/statistics.py` owns quality/quantiles/absolute demand; `optimizer.py` owns
capacity and compatibility gates, replay and selection; `costs.py` owns Decimal
arithmetic; `alerts.py` owns descriptive telemetry detection. No event/oracle label
is used as a detector. `engine/service.py` is the common boundary for filtered
inventory, summaries, simulation, decisions, plan reconciliation and exports.
HTTP handlers validate inputs and serialize these shared service results.

Decisions and audit entries are separate from derived recommendations. A decision
transaction checks the snapshot and revision before writing both records. A review
finding can be queued without becoming a financially effective action. The plan
recomputes each selected resource's authoritative cost once and retains separately
billed attachments. Unknown prices remain absent from explicitly partial totals.

The frontend reads all application data through `/api`. Lists use compact summary
contracts; full candidate evidence is fetched when a drawer opens. Charts request
hourly/daily aggregates containing means, peaks, expected and valid sample counts.
Missing buckets remain absent observations. Combined filters are applied to the
same inventory scope used by costs, recommendations, charts, alerts and exports.

The local execution lab can apply separately approved changes to LocalStack or
create a GitHub PR for the supported demo Terraform mapping. It does not apply
production cloud changes. Forecasting and what-if scenarios are available in
Monitoring; they do not override optimizer gates or install schedules. The AWS
hosted configuration disables the execution lab.

For local setup and a project overview, read
[the README](../README.md).
