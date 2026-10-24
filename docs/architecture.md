# Application architecture

The existing local stack is retained: FastAPI + Pydantic, SQLite, React + TypeScript
and Vite/Tailwind. Analysis uses Python's standard library; there are no new runtime
dependencies, trained models or external services.

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

Provider execution is absent. A future dedicated Docker lab must be an isolated
adapter with exact approval, measurements and verified restore. Forecasting is a
separate future demand input and can never override the optimizer's hard gates.
