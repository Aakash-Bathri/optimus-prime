# CloudPilot AWS investor demo (Mumbai)

This is a **single-instance, password-protected MVP demo**, using the existing
synthetic benchmark. It is not a highly available or securely multi-tenant SaaS.
Nothing is deployed until you run the apply commands below in your AWS account.

## What gets deployed

- `bootstrap/`: immutable private ECR repositories and an empty Secrets Manager entry.
- `demo/`: dedicated VPC/public subnet, Amazon Linux 2023 `t3.medium` EC2, static
  Elastic IP, encrypted root disk and separate encrypted 30 GiB persistent data disk.
- Caddy automatically provisions HTTPS for a domain you own. Gateway credentials
  protect **both the website and all API paths**. The app's browser profile remains
  a demo preference, not an account or tenant identity.
- Frontend and backend use internal Docker networking. Only Caddy publishes ports
  80/443; port 80 serves certificate validation and HTTPS redirects. No SSH, API,
  database or Docker socket is exposed. SSM provides administrative access.
- Qwen and gateway credentials are loaded from Secrets Manager at runtime into
  root-only files under `/run`. Terraform manages no secret versions or values.
- Hosted backend removes the execution API and never initializes its execution
  service. Hosted frontend removes the execution lab navigation and action buttons.
  Local Compose behavior remains unchanged.
- Docker logs go to CloudWatch (14 days). EC2 status/CPU alarms publish to an SNS
  topic; notifications require a confirmed subscription you configure separately.
- Daily SQLite-consistent backups (02:00 UTC) are retained seven days on the data
  disk. AWS Backup snapshots the disk daily after 03:00 UTC, with configurable
  retention. A failed SQLite backup does not block AWS Backup: snapshots are
  independent crash-consistent recovery points; check both jobs during operations.

The VM's instance role can retrieve only the chosen secret and the two chosen ECR
repositories, plus write logs and register with SSM. IMDSv2 is required; a metadata
hop limit of one prevents ordinary bridge-network app containers using the VM role.
Caddy has one shared investor credential; rotate it between demo rounds.

## Prerequisites

- AWS account and AWS CLI v2 credentials for **real AWS**, with permission to create
  VPC/EC2/EBS, ECR, IAM roles/policies, Secrets Manager, AWS Backup, CloudWatch and SNS.
  Route53 permission is needed only if using its optional DNS record.
- Terraform 1.10+, Docker with Buildx, Python 3 and a domain you own.
- Choose Mumbai (`ap-south-1`, the default). A domain is required before applying
  `demo/`; you can complete bootstrap, image upload and secret setup before buying it.
- For the optional `.env` import helper, use `backend/.venv/bin/python` after backend
  dependency setup; it supplies `python-dotenv`.

From the repository root, select your AWS profile and verify the account:

```bash
export AWS_PROFILE=your-deployment-profile
aws sts get-caller-identity
```

Remove any `AWS_ENDPOINT_URL*` variables from local LocalStack experiments. This
configuration has no LocalStack endpoints and uses no dummy credentials. Do not
source the application `.env` as a shell script. No AWS credentials need to be put
in Terraform files, container images, cloud-init, or the app's runtime secret.

## 1. Create image repositories and the secret entry

```bash
terraform -chdir=infra/aws/bootstrap init
terraform -chdir=infra/aws/bootstrap plan -out=bootstrap.tfplan
terraform -chdir=infra/aws/bootstrap apply bootstrap.tfplan
terraform -chdir=infra/aws/bootstrap output
```

Defaults are Mumbai and `cloudpilot-demo`. If changing them, copy
`bootstrap/terraform.tfvars.example` to `bootstrap/terraform.tfvars` first, and use
matching region/project settings in `demo/`.

Both roots use local state initially. Before shared/team use, create an existing
private S3 state bucket with encryption, versioning and restricted access, copy
`backend.s3.tf.example` to `backend.tf` in **each** root, and set distinct state
keys (`cloudpilot/bootstrap.tfstate` and `cloudpilot/demo.tfstate`). Then run
`terraform init -migrate-state` in each root. The S3 example enables lockfiles.
State, plans, local tfvars and backend configuration are gitignored. Commit the
provider lock files. Do not lose the state files or apply from a different directory.

## 2. Build and push the hosted images

```bash
bash infra/aws/scripts/build-push.sh
```

The script prints the immutable ECR image references to use in the next step.
It builds **linux/amd64** images even when run on an Apple Silicon Mac. Supply a
fresh unique version tag as its first argument if desired. Reusing a tag fails
because ECR tags are immutable. The script creates no compute resources and does
not apply Terraform. It logs out of ECR when finished.

The hosted images intentionally exclude the Terraform CLI, Node runtime and
LocalStack integration files from the backend. The same locked Python dependencies
are used, but the application runs as non-root UID 10001 and with a read-only root
filesystem. The frontend calls `/api` on the same HTTPS origin.

## 3. Populate the runtime secret outside Terraform

Copy `runtime_secret_arn` from bootstrap outputs, then run:

```bash
backend/.venv/bin/python infra/aws/scripts/configure-secret.py \
  --secret-arn 'arn:aws:secretsmanager:ap-south-1:ACCOUNT_ID:secret:YOUR_SECRET' \
  --env-file .env
```

It prompts for a demo username and a new access password (minimum 16 characters),
hashes the password using Caddy, and uploads only the demo gateway credentials and
Qwen fields. The upload uses stdin; neither the password nor API key is passed as
a process argument or saved to a local plaintext file. AWS deployment credentials
must already be supplied through your CLI profile/session.

The helper accepts `QWEN_API_KEY`, `QWEN_BASE_URL`, `QWEN_MODEL`, falling back to
`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `CLOUDPILOT_LLM_MODEL` from the explicitly
provided file/environment. These support the existing Qwen Bedrock Mantle
OpenAI-compatible endpoint. There is no need to enable a native Bedrock SDK role.
To run rules-only, omit the env file and unset all six LLM variables in the shell.

Alternatively, populate the secret in the AWS console with this schema:

```json
{
  "DEMO_USERNAME": "investor",
  "DEMO_PASSWORD_HASH": "<bcrypt cost 10–16 hash, not the password>",
  "QWEN_API_KEY": "<your existing API key>",
  "QWEN_BASE_URL": "<your HTTPS OpenAI-compatible endpoint ending in /v1>",
  "QWEN_MODEL": "qwen.qwen3-coder-480b-a35b-instruct"
}
```

All three Qwen fields must be present together, or all omitted for rule-based mode.
The runtime loader fails closed if gateway credentials are absent or invalid.
Do not put the secret JSON into tfvars or create a `aws_secretsmanager_secret_version`.

## 4. Configure your domain and deploy compute

```bash
cp infra/aws/demo/terraform.tfvars.example infra/aws/demo/terraform.tfvars
```

Edit `terraform.tfvars` with:

- Your real `domain_name` and `acme_email`.
- The exact two ECR image references printed by the build script.
- The populated `runtime_secret_arn` from bootstrap.
- Optionally your existing public `route53_zone_id`. If omitted, DNS is manual.
- Optionally narrow `https_allowed_cidrs` to your and your investors' public IPs.

Then review and apply:

```bash
terraform -chdir=infra/aws/demo init
terraform -chdir=infra/aws/demo plan -out=demo.tfplan
terraform -chdir=infra/aws/demo apply demo.tfplan
terraform -chdir=infra/aws/demo output
```

If DNS is external, create an **A record** for your domain pointing to `public_ip`.
Remove conflicting AAAA records unless IPv6 routing is deliberately configured;
this stack is IPv4-only. For the first verification, use DNS-only rather than an
additional CDN proxy. Automatic HTTPS needs public DNS resolution and reachability
on port 80 for validation. The HTTPS app may remain restricted to selected IPs.

Allow 5–15 minutes for bootstrap, Docker image pulls and the first fixture import.
Terraform completing does **not** mean the app is ready. Verify it as below.
Copy the output `ami_id` into tfvars after the initial deployment if you want to
pin the OS image and avoid replacement when AWS publishes a new AMI.

## 5. Verify before inviting investors

Open `demo_url` in your browser. The gateway must request the new username/password
before displaying the local demo-profile screen. Use its demo profile to enter.

These checks prompt for the access password; it does not enter command history:

```bash
# Must return 401 without credentials.
curl -I https://demo.yourcompany.com/api/health
# Must return JSON status=ok.
curl --user investor https://demo.yourcompany.com/api/health
# Must return 404 even with valid gateway credentials.
curl --user investor https://demo.yourcompany.com/api/execution/resources
```

Also confirm the forecast page works, Qwen returns a labeled explanation, reports
download, and a queued review decision survives restarting the application.
Inspect SSM/systemd and CloudWatch before assuming startup succeeded:

```bash
# Run the output ssm_connect_command locally, or use EC2 > Connect > Session Manager.
# The following commands run INSIDE the SSM session:
sudo systemctl status cloudpilot cloudpilot-data
sudo journalctl -u cloudpilot -n 80 --no-pager
sudo tail -n 80 /var/log/cloud-init-output.log
sudo systemctl list-timers cloudpilot-backup.timer
sudo docker ps
```

Do not print environment files, `docker inspect` environment arrays or the runtime
secret into logs/screenshots. SSM administrator access inherently permits reading
runtime credentials; restrict operator IAM membership accordingly.

Subscribe to the `operations_topic_arn` in SNS and confirm the subscription to
receive infrastructure alarms. Application anomaly/budget alerts still refresh
while the monitoring page is open; this deployment does not add an unattended
application alert worker or email/Slack integration.

## Updates, rollback and secret rotation

Build/push a new tag, edit both image references in tfvars, and review/apply a new
plan. Changing the bootstrap template or images replaces the VM, reattaches the
same encrypted data volume and retains the Elastic IP. This has downtime; there
is no load balancer or rolling deployment. Terraform stops the old host before
volume detachment. Never force-attach the disk to two running hosts.

Rollback: restore the prior two immutable image references, review the plan, then
apply. Database formats must remain compatible; restore a backup when a future
schema migration cannot be reversed. Pin the AMI if consistent OS rollback matters.

After updating the secret, run `sudo systemctl restart cloudpilot` via SSM. The
service retrieves current credentials and force-recreates containers. Secrets
Manager rotation alone does not update already running containers. A failed secret
load or image pull makes the unit fail/retry; inspect its status before the demo.

## Backup, recovery and cleanup

Verify a successful SQLite backup and AWS Backup recovery point after the first day.
The schedule provides approximately a one-day recovery point objective, not HA.
To recover, stop the app, restore an EBS volume from AWS Backup into the same AZ,
mount it offline, and select a verified `/database/backups/*.sqlite3` file. Preserve
the original live database/WAL files before switching to the consistent backup.
For full volume replacement, intentionally update/import the data-volume resource
and attachment in Terraform; do not just reformat or overwrite the existing disk.
Restore credentials remain in Secrets Manager, separately from disk snapshots.

`prevent_destroy` intentionally blocks deleting/replacing the data volume. If you
intend to tear down the demo: first export/retain needed data and recovery points,
then explicitly remove that lifecycle guard, review a destroy plan, and destroy
`demo/`. AWS Backup vault deletion requires recovery points to be removed/expired
first. Afterward, explicitly empty ECR repositories if no longer needed and destroy
`bootstrap/`; repository force-delete is disabled and the secret has a seven-day
recovery window. Keep any retained backups accounted for in your AWS bill.

Charges include EC2, root/data EBS, public IPv4, backups, ECR, Secrets Manager,
CloudWatch, DNS/domain, data transfer and Qwen requests. No NAT Gateway, ALB or RDS
is created. T3 CPU credits use standard mode to avoid unlimited-mode surplus credit
charges. Review Mumbai pricing and set an account budget before applying. The
app's simulated cloud-spend budget does not cap this AWS account's actual bill.

## Local validation (no AWS resources)

```bash
terraform -chdir=infra/aws/bootstrap init -backend=false
terraform -chdir=infra/aws/bootstrap validate
terraform -chdir=infra/aws/bootstrap test
terraform -chdir=infra/aws/demo init -backend=false
terraform -chdir=infra/aws/demo validate
terraform -chdir=infra/aws/demo test
```

Tests use Terraform mock providers. They exercise IAM scope, encryption, metadata
protection, ingress, backup configuration and immutable image validation. The
separate template check exercises the EC2 user-data limit.
The demo tests use plans so the data-volume deletion guard remains in effect.
They do not test an actual AWS boot, ACME issuance or AWS Backup restore. A real plan
requires your account credentials and chosen hostname; live deployment verification
remains a step to perform in that account.

References: [AWS Secrets Manager runtime retrieval](https://docs.aws.amazon.com/cli/latest/reference/secretsmanager/get-secret-value.html),
[AWS EBS attachment behavior](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/volume_attachment),
[Caddy authentication](https://caddyserver.com/docs/caddyfile/directives/basic_auth),
[Docker Compose installation](https://docs.docker.com/compose/install/linux/).

For additional local checks (Docker required for the last two commands):

```bash
python3 infra/aws/scripts/validate-templates.py --docker
docker build -f infra/aws/backend.Dockerfile -t cloudpilot-backend:aws-check .
docker build -f infra/aws/frontend.Dockerfile -t cloudpilot-frontend:aws-check .
python3 infra/aws/scripts/smoke-local.py
```

The smoke test uses temporary data, test credentials, an isolated Compose project
and randomly assigned loopback ports. It verifies HTTPS using Caddy's temporary
local CA, anonymous API denial, execution API absence, forecasts, non-root backend,
SQLite restart persistence and a consistent backup. It cleans up its own containers
and never sends requests to AWS or alters the existing local demo.

If increasing `data_volume_gib`, EBS expansion does not automatically grow ext4;
use SSM to identify the data volume and run `resize2fs` after the size change.
