# CloudPilot: technical requirements

## Goal
Help an engineer find wasted cloud capacity, understand a specific recommendation and test an approved change or create a Terraform PR.

## Architecture
**React → FastAPI → SQLite.** One frontend, one backend and one database. No worker queue, vector database or autonomous agent loop.

The backend does three jobs:

- **Analyze:** validate the local CSV/JSON dataset and recheck its hashes before publishing; calculate peak utilization, safe capacity candidates and cost differences; store evidence and decisions.
- **Explain:** one shared HTTP client calls the configured LLM for plain-language what-if questions, findings and execution previews. The backend validates scenario inputs and performs all calculations. The LLM has no tools or execution authority.
- **Execute:** create an exact preview, require approval, recheck evidence and live state, then change a tagged LocalStack fixture through MCP or create a GitHub PR.

Code: `adapters/` and `repositories/` import data; `engine/` calculates findings and scenarios; `agent/language.py` handles text calls; `execution/` owns approvals and integrations. React lives in `frontend/src/`.

## User flow
Open the workspace directly. Filter resources and inspect history. Review a finding and queue it. In Execution lab, register a destination, choose a candidate and prepare the preview. Approve it, execute separately and inspect the verified result.

Manual resizing preserves the starting running/stopped state. An inverse change requires fresh approval. Terraform creates a PR; the customer reviews, merges and applies it.

For what-if questions, the LLM fills visible scenario inputs. The user reviews and runs them. Unsupported questions request clarification. A model failure leaves manual inputs usable and labels explanation fallbacks.

## Rules
1. Missing telemetry, prices and provider capabilities remain visible. Unknown prices are excluded from known-charge totals; unpriced resources remain in inventory and drilldowns.
2. Capacity checks use observed peaks and stress replay. Historical synthetic evidence cannot authorize Utho production changes.
3. Quarterly compute price divided by three is a comparison basis. Stopping committed VMs saves zero cash. Hourly prorating is an explicit hypothetical assumption.
4. Scenarios count actual elapsed local time, including daylight-saving changes. Energy and carbon use editable assumptions.
5. Approvals bind the source revision, resource snapshot, target and Terraform commit. Changed evidence requires a fresh preview. Repeating completed execution returns its saved result. Ambiguous writes require inspection of both local and remote effects.
6. Secrets stay on the server except the local operator token held in page memory. Local filters are not tenant authentication.

## Verification and limits
Run `pytest` in the backend and the frontend production build. Automated API journeys use simulated external adapters; live MCP, LLM and PR evidence is recorded separately in `docs/verification/`.

Forecasts are historical extrapolations. Production Utho execution, automatic deletion, secure tenancy and unattended notifications are outside the implemented prototype. Actual Terraform PRs support the audited demo module only. See `PRODUCT_AUDIT.md` for detailed corrections.
