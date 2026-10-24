# Product audit and correction record

Reviewed against the Utho SmartCloud Optimizer statement (PDF pages 44–47), not the unrelated challenges in the same document. This is a record of concrete findings, not a claim that hundreds of independent defects were discovered or that every possible defect is fixed.

| Finding | Correction |
|---|---|
| Scenario shutdown savings contradicted quarterly commitments | Default commitment mode produces zero cash savings; hourly prorating requires explicit selection. |
| Scenario form had no natural-language what-if input | Added a bounded LLM interpretation endpoint and question form. |
| LLM weekday convention produced Tuesday–Saturday for “weekdays” | Added explicit Monday=0 mapping in the schema and prompt; live verification checks Monday–Friday. |
| LLM scenario fields could omit inputs and silently fall back to defaults | Require a complete scenario and validate every field. |
| Unsupported LLM requests could turn into invented actions | Return clarification for unsupported requests; model has no execution tools. |
| An old what-if response could overwrite newer edits | Compare the question, scope and draft before accepting the response. |
| Findings required leaving the drawer to get an LLM explanation | Added plain-language explanation directly to each finding. |
| LLM explanation incorrectly used a dollar symbol for INR amounts | Include currency and scenario in its context and explicitly require INR without conversion. |
| Explanation could mix estate savings with a resource finding | Prompt explicitly separates resource evidence from estate scenario totals. |
| Local profile screen blocked access without providing authentication | Removed the profile gate and account controls. |
| Single-option organization selector implied switching capability | Replaced it with a plain local dataset label. |
| Role selector changed presentation but provided no permissions | Removed the cosmetic role selector. |
| Terraform export contained metadata but could not implement a change | Removed the placeholder download and endpoint; real PR workflow remains. |
| Execution registration was separated from execution | Moved registration into Execution lab. |
| Registering a destination silently selected the fixture-example source | Preserve the engine finding workflow. |
| Opening a finding could show destinations before any registration | Registration is now on the destination page. |
| Manual operator token entry was unavailable when prefill was disabled | Added a deliberate connection form; token stays in memory. |
| Execution page fetched integrations while hidden | Mount it only when selected. |
| Page retained a selected proposal when management destination changed | Clear proposal selection when switching destination management. |
| Validation errors collapsed to a generic HTTP status | Shared API client displays server validation messages. |
| Paginated loading could silently accept truncated results | An unexpected empty page now asks the user to refresh. |
| A stale explanation error could appear under a new scope | Gate explanation errors by request context. |
| Export/explanation controls could run during evaluation | Disable them while the scenario is being evaluated. |
| Workspace Refresh did not refresh the mounted scenario page | Remount monitoring on an explicit workspace refresh. |
| Scenario heading always claimed a development shutdown | Replaced it with “Scenario inputs”. |
| Unbounded alert cards buried explanations and exports | Show eight matching alerts, with an explicit show-all control. |
| Identical telemetry alerts omitted the affected resource | Display the resource name with the alert. |
| Growth could project utilization above 95% but retain warning severity | Severity now uses projected utilization. |
| Estimated busy hours could exceed allocated hours | Bound the estimate by available capacity. |
| Scenario repeatedly recalculated invariant cost shares inside its daily loop | Calculate scoped cost shares once. |
| Local timezone schedules were anchored to UTC calendar midnight | Anchor each forecast day at local midnight before evaluating hourly windows. |
| Browser navigation left a drawer covering the newly selected page | Close the drawer on route changes. |
| A stale finding retry kept requesting the obsolete recommendation ID | Refresh the workspace and close the outdated drawer when the dataset version has changed. |
| Development proxy could only target port 8001 | Added a server-only configurable API proxy target. |

| Zero known expense totals were presented as a complete bill | Label known charges and show unpriced counts in expense drilldown summaries. |
| Unpriced and zero-cost resources vanished from expense drilldowns | Keep every scoped resource in the drilldown, including unavailable charges. |
| “Unassigned” expense groups could not match resources without teams | Apply the same missing-team label to filtering and grouping. |
| Shutdown hours assumed a 24-hour local day across DST | Count actual elapsed quarter-hours; verify 23, 25 and 23.5 hour days. |
| Energy and allocated capacity ignored DST horizon duration | Use actual elapsed horizon hours for both estimates. |
| Monthly cost alerts treated February–March day count as spending growth | Compare daily-normalized rates consistently across alert paths. |
| Zero-to-positive costs were hidden or called a 100% increase | Raise a new-cost alert and label percentage growth undefined. |
| Execution preview required an agent loop for an already chosen action | Use one bounded explanation call; the server keeps the immutable action. |
| Explanation, what-if and execution used separate model integrations | Share one HTTP text client, configuration and response validation. |
| Configured non-Qwen models were silently skipped for explanations | Accept the configured compatible model and label its LLM output. |
| The preview displayed framework names and fake model tool steps | Show the explanation source; no tool execution is attributed to the model. |
| Duplicate category cards repeated the full recommendation table | Keep category filtering in the table and remove the duplicate card grid. |
| Explicit refresh did not reload the expense explorer | Include refresh in the expense request dependencies. |
| Dataset replacement could retain an old expense date range | Reset the explorer when the dataset version changes. |
| Candidate controls could change while evidence was loading | Disable execution inputs while a workflow request is running. |
| A finding removed from the queue retained usable candidate selections | Clear its evidence and disable preparation when it is no longer queued. |
| Current instance shapes appeared as selectable resize targets | Mark current shapes and disable no-op previews. |
| The single-source filter added a redundant choice to every page | Show source selection only when more than one source exists. |
| Execution offered arbitrary demo actions beside evidence-backed findings | Remove the competing fixture-action form; all UI previews start from a queued engine finding. |
| Unknown scenario fields were silently ignored and defaults ran instead | Reject unsupported input fields and nonfinite numbers during validation. |
| Missing-team resources had no option in the global team filter | Expose the same Unassigned option used by expense groups. |
| A resource fallback explanation included unrelated estate scenario totals | Limit fallback text to that finding’s costs, evidence and blockers. |
| Mobile filters and wide evidence tables could expand the entire page | Bound the flex workspace and use a two-column filter grid on narrow screens. |
| Empty execution instructions still referred to registration on Home | Point users to the registration controls on the same page. |

| Duplicate or blank CSV headers silently overwrote input values | Reject ambiguous column names before parsing any records. |
| Empty or whitespace-padded source IDs were treated as real identities | Reject those identities before joining inventory, prices or evidence. |
| Fractional or boolean telemetry intervals were coerced into integers | Require an integer interval within the supported 5–15 minute range. |
| Manifest counts could contradict the observation grid and resource totals | Validate duration, points, VM/GPU row counts and resource totals together. |
| Incomplete or duplicate-key JSON manifests failed ambiguously or lost values | Require the manifest structure and reject duplicate fields explicitly. |
| Invalid monetary text raised a low-level Decimal exception | Return a source validation error. |
| Inventory/catalog comparison omitted transfer allowance | Include it in the VM configuration consistency check. |
| Inventory could attach a VM to another VM or attach a child to a non-VM | Require supported child resources to reference a VM host. |
| Status, lifecycle and attachment fields could contradict one another | Validate their supported combinations before analysis. |
| Explicitly invalid observation rows could still contribute all their numbers | Exclude all measurements from rows already marked invalid. |
| GPU inventory accepted a nonpositive VRAM capacity | Require a positive declared capacity when available. |
| GPU usage could exceed its declared physical memory | Reject observations above the known device capacity. |
| Relationship rows could contradict inventory type or host | Validate each relationship against the actual child attachment. |
| Duplicate or missing attachment relationships were accepted | Require exactly one matching edge for each declared attachment. |
| Source events could claim nonsynthetic provenance or lack an identity | Validate those fields before importing them. |
| Events could end before they started | Validate chronological order. |
| Naive event timestamps were displayed in the browser’s local timezone | Normalize imported event timestamps to the dataset’s assumed UTC convention. |
| Malformed event severity values reached the UI unchecked | Validate the supported source severity vocabulary. |
| Noncanonical billing months broke lexical ordering | Require exact YYYY-MM month values. |
| Missing billing months or a wrong history length changed projections silently | Validate consecutive months and the manifest’s history length. |
| Duplicate resource/month charges produced a database exception | Reject them with a named billing-source diagnostic and atomic rollback. |
| Source files could change after fingerprinting but before publication | Recheck source hashes before committing the imported snapshot. |
| Presentation-only changes invalidated every rightsizing decision | Fingerprint only code that produces stored import and analysis results. |
| Successful GitHub responses containing invalid JSON escaped as internal errors | Validate response type and return a sanitized integration diagnostic. |
| Malformed base64/UTF-8 repository files failed without useful context | Reject invalid source encoding explicitly. |
| An invalid GitHub App PEM produced an internal error | Report a configuration error without exposing the key. |
| Malformed cloudpilot.json mappings failed as arbitrary exceptions | Require a resources array of mapping objects and a supported root module. |
| A timeout during remote branch creation could release the resource lease | Audit the write attempt first and require recovery for ambiguous results. |
| Terraform recovery inspected only LocalStack, ignoring possible GitHub effects | Inspect the deterministic branch and existing PR, then expose that result before another change. |
| Terraform variable files could be JSON arrays rather than objects | Refuse them before preview validation. |
| Terraform timeout or process-start failure had no actionable diagnostic | Distinguish timeout and installation failures; create no preview. |
| CSV names with leading whitespace bypassed formula escaping | Inspect leading whitespace before escaping formula-like text. |
| CSV plan IDs, blockers and other text fields bypassed formula escaping | Escape all textual export fields while preserving numeric cost columns. |

| MCP timeouts and tool failures became unhelpful internal errors | Return bounded, sanitized integration errors. |
| State polling could multiply a 45-second request timeout across 30 attempts | Enforce one total transition deadline. |
| Missing MCP content fields could crash response parsing | Treat malformed responses as controlled integration failures. |
| A deleted fixture could permanently block recovery and re-registration | Record absence from live inventory and release the failed execution after acknowledgement. |

## Verification boundaries

The existing tests cover input integrity, peaks and memory safety, source fingerprints, transactional decisions, exports, stale approvals, interrupted execution and provider gates. Added regression coverage protects commitment billing and malformed LLM scenarios. Fifteen automated API journeys exercise real data and engine logic with simulated cloud/GitHub adapters. Live MCP, LLM and PR evidence is stored separately in `verification/`.

## Remaining product limits

The source evidence cannot justify production Utho mutations or verified savings. Secure tenant/role authorization is absent. Forecasts are simple historical extrapolations, not trained or calibrated predictions. Sustainability remains an assumption-based estimate. The UI still has separate cost, inventory and source views, which expose useful evidence rather than fabricated actions. Review-only deletion and orphan findings remain blocked until ownership, retention and provider support are verified.
