# Person 5 prerequisites

This setup prepares the integrations for the agreed five-step plan. The agent,
approval UI and PR/change workflows are implemented; see [workflow usage](PERSON_5_WORKFLOW.md).

Verified on 24 October 2026: Bedrock LangChain tool round trip, official MCP
inventory lookup through the LangChain adapter, both LocalStack demo fixtures,
GitHub App repository read/write, Terraform validation and initial apply,
two backend tests and the frontend production build. These checks establish
integration readiness. The workflow guide describes the separate acceptance tests.

## Configuration

The ignored root `.env` contains the LocalStack token, Bedrock Mantle configuration,
GitHub App ID and private-key path. The key directory and all PEM files are ignored.
Never copy actual credentials into `.env.example` or the Terraform repository.

Bedrock matches the supplied `gate_pass` setup:

- Endpoint: `https://bedrock-mantle.us-east-1.api.aws/v1`
- Model: `qwen.qwen3-coder-480b-a35b-instruct`
- LangChain integration: `ChatOpenAI`, Chat Completions, `use_responses_api=False`.
- Use explicit output limits. The connection check uses 256 output tokens per call.
- The API key was transferred locally; it is not included in tracked files.

GitHub App: `optimus-prime-utho`. Contents and Pull requests require write access.
The App ID/private key authenticate the bot. Client ID/secret are needed only if
implementing GitHub user authorization in the dashboard.

Test repository: https://github.com/Harshavardhan2903/cloudpilot-terraform-demo

Its README has the app installation link. Select this repository during installation.
`cloudpilot.json` maps `demo-api-01` to `aws_instance.production_api`, and
`terraform.tfvars.json` holds the editable instance type.

## Commands from the project root

```powershell
# Start the pinned LocalStack container and wait until healthy.
.\infra\start_localstack.ps1

# Launch the pinned official MCP server over stdio. An MCP client normally runs this.
uv run --directory backend python ../infra/run_localstack_mcp.py

# Read-only integration checks; 'llm' and 'all' make small billed Bedrock requests.
uv run --directory backend python ../infra/check_prerequisites.py all

# Terraform CLI is installed in the user's existing .local/bin PATH directory.
terraform -chdir=infra/demo-terraform init
terraform -chdir=infra/demo-terraform validate
terraform -chdir=infra/demo-terraform plan

uv run --directory backend pytest
npm --prefix frontend run build
```

Check results are saved in ignored `data/local/prerequisites.json`. Failed checks
remain failed. The MCP check requires a parsed EC2 inventory response, because
the official server sometimes returns error text without setting `isError`.

## Demo resources

The initial Terraform apply creates `cloudpilot-production-api`, tagged
`CloudPilotId=demo-api-01` and `Management=terraform`. State remains in the ignored
local Terraform directory. The GitHub repository includes the provider lock file.

The manual fixture is `cloudpilot-manual-dev`, tagged
`CloudPilotId=demo-manual-01` and `Management=manual`. Recreate it if needed with:

```powershell
uv run --directory backend python ../infra/seed_manual_demo.py
```

Both start at `m5.2xlarge`. Provider instance IDs are recorded in the check report;
the manual mapping is also in ignored `data/local/manual-demo.json`.
The installed GitHub App's installation ID is saved in the root `.env`.

The current LocalStack license does not include the snapshot plugin, and a
container restart was observed to reset the EC2 records. The named volume keeps
the license cache; it does not guarantee resource persistence. After a restart,
recreate both fixtures with `./infra/seed_demo.ps1`, then rerun the checks.
See [LocalStack persistence](https://docs.localstack.cloud/aws/developer-tools/snapshots/persistence/)
for the separately licensed persistence feature.

## Local addresses

- LocalStack: `http://127.0.0.1:4566`, container `cloudpilot-localstack`.
- Backend: use port **8001** because another application already owns port 8000.
- Frontend: `http://localhost:5173`; local configuration points it to port 8001.

```powershell
uv run --directory backend uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
npm --prefix frontend run dev
```

The EC2 resources are LocalStack control-plane records. They are separate from
the synthetic Utho estate and do not establish workload performance or real savings.
The Terraform repository contains no cloud credentials or checked-in state.
