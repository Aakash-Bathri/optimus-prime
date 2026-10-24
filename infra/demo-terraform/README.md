# CloudPilot Terraform demo

Dedicated test infrastructure for Person 5's GitHub PR workflow. All provider
endpoints point to LocalStack on this computer; no real AWS credentials are used.

[Connect this repository to CloudPilot](https://github.com/apps/optimus-prime-utho/installations/new)

Select your account, choose **Only select repositories**, select
`cloudpilot-terraform-demo`, and install. If the app is already installed, use
its configuration page to add this repository. This grants the CloudPilot bot
access to this repository; it does not deploy or modify infrastructure.

The production API starts at `m5.2xlarge` (8 vCPU, 32 GiB). A future recommendation
can propose `m5.xlarge` (4 vCPU, 16 GiB) by changing `api_instance_type` in
`terraform.tfvars.json`. The smaller `m5.large` is a separate candidate whose
eligibility must be evaluated. A proposal is not proof of workload safety.

`cloudpilot.json` maps the application's `demo-api-01` ID to its Terraform
address and editable variable. No telemetry or recommendations are fabricated
by this infrastructure. Utho city labels are illustrative; LocalStack uses the
AWS region `us-east-1`. Prices and savings must come from the application.

Start the CloudPilot LocalStack container, then run Terraform init, validate,
plan and apply from this folder. Keep the local state files private. Opening
or merging a PR does not apply it; the client owns apply.
