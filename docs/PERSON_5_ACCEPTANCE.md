# Person 5 acceptance — 24 October 2026

Scope: the agreed LocalStack → official MCP → LangChain agent workflow, with an
approved GitHub Terraform PR path and an approved direct manual-resource path.

| Requirement | Evidence | Result |
| --- | --- | --- |
| LocalStack Docker | `cloudpilot-localstack` reports healthy; real EC2 inspection | Passed |
| Official MCP + LangChain | Official 0.7.0 AWS tool invoked through the LangChain adapter | Passed |
| Bedrock agent | Actual Mantle/Qwen requests call inspect_resource, read_terraform for Terraform, and prepare_change | Passed |
| Terraform preview | Pinned GitHub source, exact variable diff, offline pinned-provider fmt and validate | Passed |
| Approved real PR | [Test PR #1](https://github.com/Harshavardhan2903/cloudpilot-terraform-demo/pull/1) is open; only terraform.tfvars.json changes m5.2xlarge → m5.xlarge | Passed |
| Customer-controlled apply | PR was not merged; Terraform-managed LocalStack snapshot unchanged | Passed |
| Manual resize | Real MCP stop → resize → start; reread confirmed m5.xlarge/running | Passed |
| Manual restore | New inverse preview, new exact approval, reread confirmed original m5.2xlarge/running snapshot | Passed |
| Reject/unapproved execution | Real rejection leaves LocalStack unchanged; both route boundaries also covered by unit tests | Passed |
| Repeat execution | Repeating completed proposal returns the same result and does not create another PR/change | Passed |
| Stale evidence/configuration/ownership/mapping/base | Unit tests prove execution is blocked | Passed |
| Concurrency and partial failures | Unit tests cover leases, verification failure, recovery acknowledgement and restart recovery | Passed |
| Agent cannot change engine target | Real LangChain graph with a fake model rejects altered target arguments | Passed |
| Persistence | SQLite proposals and audit reloaded; actual running HTTP server exposes saved history | Passed |
| Backend checks | `uv run --directory backend pytest -q`: 25 passed | Passed |
| Frontend check | TypeScript/Vite production build passed; browser rendered API-connected inventory and execution form | Passed |
| Credential handling | Scan of tracked and non-ignored files found none of the configured secret values | Passed |

Live results are stored locally in `data/local/person5-live.json`; current runtime
HTTP checks are in `data/local/person5-http.json`. Real integration tests were run
in addition to unit tests with fake providers. A final current-code Terraform
agent preview also passed and remains awaiting approval; it did not create another PR.

Demo evidence is explicitly stubbed. No forecast accuracy, workload benchmark,
production-safe downsizing, savings, real AWS/Utho mutation, arbitrary Terraform
module support or GitHub OAuth sign-in is claimed. Candidate PR validation is
fmt/validate, not a Terraform plan. Other team members' product features remain
outside this integration acceptance.
