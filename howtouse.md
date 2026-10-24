# CloudPilot: a plain-English guide

Read this document first. It explains the current project, including the dashboard,
Qwen, MCP, the execution lab and GitHub pull requests.

For the quickest start, follow the example in section 3. Sections 4–8 explain the
screens and what happens behind them. Sections 9–10 are optional lab walkthroughs.

## 1. What is this project for?

CloudPilot helps someone answer three questions:

1. Where is our cloud money going?
2. Which resources might be too large, too busy or unused?
3. What should we review before making a change?

For example: a team pays for a large virtual machine, but its workload uses only a
small part of its capacity. CloudPilot checks the recorded usage, compares smaller
sizes and explains which checks still need to pass.

**What you have today is a working demo with historical sample data. The main
dashboard is not connected to a customer's live cloud account.**

There are three separate parts:

| Part | What it does today |
|---|---|
| Dashboard | Reads the supplied Utho sample inventory, usage and billing. Shows costs, findings and simulations. |
| Execution lab | Tests a reviewed change against fake AWS resources in LocalStack, or opens a real GitHub PR for the supported demo Terraform repository. |
| AWS deployment files | Let you host CloudPilot itself in AWS Mumbai. Hosting the app does not connect the dashboard to your AWS bill. |

A resource you see in the dashboard and the fake machine used in the lab are
**different resources**. The lab can copy a candidate's CPU/RAM size to test the
change process. It does not resize the original Utho resource.

## 2. A few words the interface uses

| Word | Plain meaning |
|---|---|
| VM / virtual machine | A rented computer in the cloud. |
| CPU / vCPU | The processing capacity of that computer. |
| Memory / RAM | Space the computer uses while programs are running. GiB is a unit of memory. |
| Utilization | How much of a resource's capacity is being used. |
| Telemetry | Recorded measurements such as CPU usage over time. |
| p95 | A value that 95% of the recorded measurements were at or below. It is not the highest measurement. |
| Rightsizing / resize | Choosing a machine size that better fits the workload. Sometimes this means a larger machine. |
| Orphaned resource | Something that may no longer be attached or needed, such as a disk. It still needs an owner to check it. |
| Finding / recommendation | Something the app thinks a person should investigate. |
| Blocker / prerequisite | A fact that must be checked before treating a change as ready. |
| Conditional savings | Money that might be avoided if the assumptions and required checks turn out to be correct. |
| Evidence cutoff | The last date covered by the imported data. It tells you how old the evidence is. |

## 3. A simple user journey, from opening the app to a useful result

Imagine Priya is an engineer investigating development spending.

1. **Open the app and choose Use demo profile.** On the hosted version, first pass
   the separate gateway username/password prompt.
2. **Open Home.** Read the spending period and evidence cutoff. Remember this is
   the sample organization, not Priya's own cloud account.
3. **Filter to Development.** This narrows the estate she is investigating.
4. **Open Cost Explorer.** Identify which resources account for the spending.
5. **Open Resources, then a resource's side panel.** Check usage, owner and linked
   findings before deciding that it should be smaller or switched off.
6. **Open Recommendations.** Read one resize finding, including its blocked or
   unknown checks. Queue it for review if it is worth investigating.
7. **Open Monitoring & forecast.** Leave the shutdown environment as Development,
   use 20:00–08:00, choose 30 days and enter a budget for those 30 days.
8. **Click Run scenario.** Compare the baseline, conditional cost avoidance and
   capacity alerts. Check the assumptions, not just the largest savings number.
9. **Click Explain with Qwen** if she wants the finding or scenario restated in
   ordinary language.
10. **Export the report.** Share it with the resource owner or finance colleague
    to discuss the next action.

**This is a complete dashboard workflow. Nothing has been changed in the cloud.**
The result is an explained, documented decision to investigate. A real customer
connection and production implementation are further work.

## 4. What every dashboard page does

### Home — “What should I look at first?”

This is the overview. It shows expenses, possible savings, resource counts, billing
history, expensive resources and groups of recommendations.

- **Organization expenses** means known charges for the displayed period.
- **Possible monthly savings** is an estimate to investigate, not money already saved.
- **Resources** includes machines, disks, public IPs and GPUs.
- **Data sources** tells you where the displayed information came from.

Start here, then open an expensive resource or a recommendation.

### Resources — “What are we paying for?”

This is the inventory. Each row represents one resource. You can see its name,
team, environment, size, known cost and available usage statistics.

Click its name to open the side panel. That panel shows usage, ownership,
dependencies and linked findings. A dash or “Pricing unavailable” means the app
does not have that price; it does not mean the resource is free.

### Cost Explorer — “Which part of the estate caused this spending?”

Choose a date range and group expenses by team, environment, region, resource type
or data source. Click a chart bar or legend item to see the contributing resources.

The supplied billing is monthly. Daily and weekly views divide that monthly amount
across days; they are not readings from a live daily billing feed. Do not interpret
a daily bar as proof that a workload spiked on that day.

### Recommendations — “What could we change, and why?”

The app groups findings into rightsizing, capacity review, idle resources and
orphaned resources.

Open a finding and read:

1. What the app noticed.
2. The current size and proposed candidate.
3. The estimated cost difference.
4. Passed, failed and unknown checks.
5. What a person still needs to verify.

**Queue for review** saves the finding in your review queue. It changes no machine
and creates no PR. **Dismiss** records that you do not want to pursue it.

The review queue also shows current cost, accepted-plan cost and accepted modeled
savings. A queued finding can leave these amounts unchanged: if it is still
review-only or blocked, the app does not count its possible savings as an approved
cost reduction. That is why “possible savings” and “accepted savings” can differ.

The candidate comparison lets you test higher or lower demand. The app rechecks
whether a candidate would have enough capacity. This calculation does not contact
Qwen or change infrastructure.

### Monitoring & forecast — “What might happen next?”

This page combines forecasts, shutdown scenarios, alerts, explanations and reports.

**Forecast:** choose 30, 60 or 90 days. The app extends the trend in the historical
monthly billing, adjusted for different month lengths. It shows the upcoming dates
and the older evidence cutoff. The shaded chart area is a sensitivity range, not
a promise about the future. Qwen does not calculate this forecast.

**Shutdown scenario:** the default question is “What if running development VMs
were off from 8 PM to 8 AM?” You can change the environment, hours, timezone,
weekdays and assumed demand growth. Click **Run scenario** after editing inputs.

Example: a daily 12-hour shutdown avoids half of the selected machines' allocated
hours. It does not necessarily halve the bill: disks remain charged and quarterly
commitments may not credit stopped hours. The app does not install a shutdown
schedule when you run this simulation.

**Budget:** enter a budget for the entire selected forecast period. A 90-day budget
is compared with 90 days of projected cost, not one month.

**Alerts:** the page shows unusual historical usage, rising costs, capacity pressure,
missing data and possible budget overruns. Thresholds can be adjusted. It checks
again every minute while the page is open. There is currently no unattended
application alert worker sending email or Slack messages.

**Usage:** allocated vCPU-hours describe available processing capacity over time.
Estimated busy vCPU-hours use historical average CPU demand. Avoided vCPU-hours
come from the simulated shutdown schedule.

**Sustainability:** energy and carbon numbers use editable assumptions about power,
data-center overhead and grid emissions. They are estimates, not electricity-meter
readings or verified carbon savings.

**Explain with Qwen:** asks the model to describe the selected scenario or finding
in ordinary language. The calculations already exist before this button is clicked.

**Exports:** the report is a readable Markdown file; JSON contains structured data.
The Terraform handoff contains schedule metadata and findings. It is not a working
provider scheduler and cannot shut down machines by itself.

**Engineer / Finance / Leadership:** changes which details are emphasized. It does
not give different people secure permissions. Team filters are also filters, not
tenant-access controls.

### Data sources — “Where did these numbers come from?”

This lists imported files and the kinds of resources they describe. The current
source is the supplied Utho benchmark. It is useful for checking the billing period,
missing measurements and unavailable prices.

There is no “connect any cloud account” onboarding flow here yet.

### Execution lab — “Can we demonstrate a reviewed change?”

This is an optional local feature. It needs LocalStack and an operator token.
It can change fake LocalStack resource records, or create a GitHub PR for the
supported Terraform demo. The AWS-hosted investor configuration disables this page
and its execution API.

The operator token is a separate credential from your Qwen key, LocalStack token
and GitHub credentials. Do not put those other credentials in its input field.

### Filters and the local profile

Environment, region, team, resource type, source and search narrow the dashboard
results. If a total suddenly looks small, check the filters before assuming data
has disappeared.

**Use demo profile** only sets a name in the browser. It is not a real sign-in.
The planned AWS demo has a separate HTTPS username/password prompt in front of
both the website and API.

## 5. How a recommendation is produced

Normal Python code makes the recommendation. It is not a model guessing a machine
size from a prompt.

The app loads the sample files into its SQLite database, checks the measurements
and compares resource sizes. It checks things such as CPU and memory demand,
missing observations, compatible hardware, storage and provider information.

For a smaller VM, it estimates how the recorded workload would fit and checks for
capacity breaches, including a more demanding stress case. If it lacks evidence,
it shows an unknown or blocked check rather than treating that check as passed.

That produces a stored finding with its evidence, candidate sizes and estimated
cost difference. Opening Home, Resources or Recommendations reads these results.
It does not launch an LLM agent for every page load.

## 6. What Qwen and the “agent” actually do

There are **two separate uses of an LLM** in this project.

### A. The explanation button in Monitoring

The sequence is:

1. You click **Explain with Qwen**.
2. The backend calculates or retrieves the scenario and finding evidence.
3. It sends the relevant figures, assumptions and optional recommendation to the
   configured Qwen endpoint.
4. Qwen returns explanatory text, which the page displays.

This is one direct chat-completion request per click. It has no tools and no power
to approve changes, modify a VM or create a PR. If the call fails, the page shows a
labeled rule-based explanation instead.

The default model configuration uses Qwen through an OpenAI-compatible endpoint.
An environment variable named `OPENAI_API_KEY` does **not** by itself mean the model
is OpenAI; the configured endpoint and model name decide which service is called.

### B. The planner in Execution lab

There is **one LangChain planning agent**, not a group of independent agents.
LangChain is the library that runs the model-and-tool conversation.

The backend has already read the selected LocalStack resource before planning.
The agent can use only these planning tools, in this order:

| Tool | What it gives the planner or records |
|---|---|
| `inspect_resource` | The snapshot and recommendation the backend has already obtained. |
| `read_terraform` | The mapped Terraform settings, only for a Terraform-managed destination. |
| `prepare_change` | The exact resource, action, target and explanation to include in a preview. |

The model asks for a tool, the backend runs it, and the model receives the result.
That can require several model calls during one preparation. It is not a continuous
background AI process. The code forces the tool order and rejects a different
resource, action or target.

The planner cannot approve or execute its own preview. Actual execution belongs to
separate backend code after your separate approval and execute clicks.

The **Agent** dropdown offers:

- **Scripted tools (no LLM):** runs the same planning steps in a fixed order. No
  Qwen request is made. This is the easiest mode for learning the workflow.
- **Bedrock Mantle + LangChain:** uses the configured LLM for that tool conversation
  and explanation. With the supplied configuration, that model is Qwen. Missing
  credentials or a failed planning call can stop preparation; this path does not
  automatically switch to the Monitoring page's rule-based fallback.

The execution planner reads the existing `OPENAI_*` and `CLOUDPILOT_LLM_MODEL`
settings. Monitoring also accepts its separate `QWEN_*` overrides. Setting only a
Monitoring override does not configure the execution planner.

## 7. What MCP does here

MCP means **Model Context Protocol**. In this project it is the connection used by
the backend to talk to the LocalStack tool server.

LocalStack is a fake AWS environment running in Docker. Its “instances” in this demo
are resource records; they are not real rented computers running your application.

The connection is:

```text
You click a lab button
  → CloudPilot backend checks the request
  → LocalStack MCP server receives an allowed AWS-style command
  → LocalStack reads or changes a fake EC2 resource
  → The backend reads it again to verify the result
  → The dashboard shows the result
```

The backend starts the LocalStack MCP server and uses its `localstack-aws-client`
tool for operations such as describing, stopping, resizing and starting instances.

MCP is the connection, not the model and not the recommendation algorithm.
**Scripted mode still uses MCP** for LocalStack operations even though it makes
no LLM calls. The regular billing dashboard does not fetch its sample inventory
through MCP, and the GitHub PR is created through GitHub's API, not MCP.

## 8. What happens when you create a PR

PR means **pull request**: a proposed code change on GitHub that a person can review.
Terraform is the code used to describe the desired infrastructure configuration.

For the supported demo, a file says:

```json
{"api_instance_type": "m5.2xlarge"}
```

A reviewed resize can propose changing it to:

```json
{"api_instance_type": "m5.xlarge"}
```

These demo sizes mean 8 vCPUs / 32 GiB and 4 vCPUs / 16 GiB respectively.

The PR path works as follows:

1. The backend checks the registered resource-to-file mapping and reads the
   configured GitHub repository at a particular commit.
2. It builds the small variable-file change in normal Python code. The LLM does
   not freely rewrite your Terraform repository.
3. Terraform formatting and validation are checked. A candidate Terraform plan
   is **not** run by this preparation step.
4. You read the diff and approve that exact preview.
5. You click **Create approved pull request**.
6. The backend checks that the resource and GitHub base commit have not changed.
   It creates a branch, commits the variable change and opens a real GitHub PR.
7. A person reviews and merges the PR, then runs the appropriate Terraform
   plan/apply workflow outside CloudPilot.

GitHub authentication uses a configured GitHub App and a short-lived installation
token. Repository access is restricted to the configured demo repository. This is
not yet a general integration that can safely edit any customer's infrastructure.

**PR_CREATED means a PR exists. It does not mean a machine changed.** Even merging
Terraform code does not apply it unless a person or separately configured CI does
that. The supplied Terraform demo targets LocalStack, so applying that demo changes
fake resources. Creating the PR still writes a real branch and PR to GitHub.

The files under `infra/aws/` are a different Terraform project: they host CloudPilot
on AWS. The execution lab does not automatically edit or apply those files.

## 9. Optional: continue into a manual LocalStack test

Use the local app with the execution lab enabled. The AWS investor configuration
intentionally stops before this workflow.

1. Ensure Docker/LocalStack is running and the demo has been seeded. For an
   existing local setup, the setup script is `bash infra/seed_demo.sh`.
2. In Recommendations, queue a resize or capacity finding that has a supported
   lab candidate. Click **Open in execution lab**.
3. Enter the `CLOUDPILOT_EXECUTION_TOKEN` value from your local `.env` into
   **Local operator token**. Click **Connect / refresh** and **Register manual demo**.
4. Keep **Queued engine finding** as the recommendation source. Select the queued
   finding and click **Load candidate evidence**.
5. Choose a supported candidate and `demo-manual-01` as the LocalStack destination.
   Choose **Scripted tools (no LLM)** for your first run.
6. Click **Prepare change preview**. Read which fake resource will change, the
   before/after size, evidence, unresolved production checks and planned steps.
7. Click **Approve this exact change**. This records approval; it still does not
   execute the change.
8. Click **Apply approved LocalStack change**. The backend rechecks the evidence
   and resource state. For a running resize, it stops the fake instance, changes
   its size, starts it again and reads the state back through MCP.
9. Check for **APPLIED** and the verified size/state. Open **Audit history** to see
   what was attempted. This verifies the change process, not workload performance.
10. To restore the old size, click **Prepare inverse change for review**, inspect
    that new preview, approve it and execute it separately.

If no supported candidate is available, the app should stop that path. Do not pick
a different resource just to force it through. **Fixture controls (stub evidence)**
is a separate demonstration with a made-up instruction; it is not an analysis-backed
recommendation. It exists to test the buttons and approval process.

## 10. Optional: take the GitHub PR route instead

Follow the lab steps above, but configure the GitHub App/repository first, use
**Register Terraform demo (GitHub required)**, and select the Terraform-managed
`demo-api-01` destination.

After preparing and approving the diff, click **Create approved pull request**.
Open the returned GitHub link and review the change. At **PR_CREATED**, CloudPilot's
part is finished. Review, merge and the demo Terraform apply are separate actions.

To undo a Terraform change after apply, restore the previous variable value through
a new reviewed PR and apply that reversal. The manual lab's inverse-change button
is not an automatic Terraform rollback.

## 11. Buttons and statuses that are easy to confuse

| Button or status | What it means |
|---|---|
| Queue for review | Save a dashboard finding for investigation. No VM change. |
| Run scenario | Recalculate a hypothetical result. No schedule installed. |
| Explain with Qwen | Make an LLM request for text. No infrastructure action. |
| Prepare change preview | Create a lab proposal, and a diff if needed. No resize or PR yet. |
| AWAITING_APPROVAL | A preview exists and needs your decision. |
| APPROVED | You approved the exact preview; execution is still separate. |
| APPLIED | The manual LocalStack operation was read back and verified. |
| PR_CREATED | The real GitHub PR was opened. Terraform has not been applied by CloudPilot. |
| STALE | The reviewed facts no longer match. Refresh, prepare and approve again. |
| FAILED | The operation failed. Read the error and audit before retrying. |
| RECOVERY_REQUIRED | A change may have partly happened. Inspect the live lab state before retrying. |

The preview has a **digest**, which is an identifier calculated from its contents.
Approval is tied to that identifier. If the resource, evidence or relevant GitHub
commit changes, the backend can refuse the old approval.

## 12. What to expect, and what not to claim

| You can demonstrate today | Still needs more work or separate verification |
|---|---|
| Browsing and filtering the supplied estate | Importing a real customer's cloud account |
| Rule-based recommendations with evidence | Production-safe changes on Utho or real AWS VMs |
| Forecasts and shutdown scenarios | A deployed scheduler that performs those shutdowns |
| Qwen explanations and a bounded planning agent | An autonomous system that can approve itself |
| A reviewed LocalStack change through MCP | Verified production workload performance after resizing |
| A GitHub PR for the supported demo mapping | General-purpose edits to arbitrary customer Terraform repositories |
| Estimated cost/energy/carbon avoidance | Measured customer savings and verified emissions reductions |
| Role presentation choices and team filters | Secure organization isolation and server-enforced user roles |
| In-page application alerts | Unattended application alert delivery to email/Slack |
| AWS hosting configuration | A live AWS deployment merely because those files exist |

For startup commands and credentials, use the main README. For hosting, use
[the AWS deployment guide](infra/aws/README.md). Earlier `PERSON_*` files are
implementation plans; use this document for the current user journey.
