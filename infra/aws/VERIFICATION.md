# AWS configuration verification

Local verification completed on 2026-10-24. **No AWS resources were created, no
images were pushed to ECR, and no real credentials were uploaded.**

Passed:

- Terraform formatting and validation in both bootstrap and demo roots.
- One bootstrap mock-provider test and two demo mock-provider plan tests.
- Rendered cloud-init shell syntax, Python syntax and compressed EC2 user-data size.
- Compose environment handling preserves literal dollar signs in keys/bcrypt hashes.
- Caddy accepts the generated authentication and HTTPS configuration.
- Both hosted Docker images build; default and hosted frontend production builds pass.
- Full backend suite: **66 passed**.
- Isolated local hosted-stack smoke test: HTTPS with a trusted temporary local CA,
  anonymous API 401, authenticated frontend/API, execution routes 404, 30-day
  forecast, non-root/read-only backend, review-decision persistence across restart,
  and an integrity-checked SQLite backup. Temporary containers/data were cleaned up.

Remaining live-account verification after deployment: IAM/account restrictions,
EC2/SSM boot, runtime secret retrieval, ECR pulls, public DNS/ACME certificate,
CloudWatch delivery, SNS subscription and a real AWS Backup recovery/restore drill.
These require your actual AWS account and chosen domain. See README.md for steps.
