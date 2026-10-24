# Local lab and infrastructure — Person 5

See [Person 5 prerequisites](../docs/PERSON_5_PREREQUISITES.md) for the configured
LocalStack, MCP, Bedrock and GitHub App integrations.

Run `./infra/seed_demo.ps1` from the repository root to start LocalStack and create
the two demo EC2 records. This applies the local Terraform fixture and creates the
manual fixture. Rerun it after a container restart because the current license
does not provide resource persistence. Product approval workflows remain to be built.

