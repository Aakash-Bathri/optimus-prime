# Terraform execution demo — 24 October 2026

Verified against the local Compose dashboard at http://127.0.0.1:5175.

- Home prefills the operator token in a password field through the opt-in, uncached local session endpoint.
- Manual and Terraform registration choices appear only on Home. Selecting Terraform opens Execution lab with the Terraform destination and demo recommendation selected.
- Terraform registration succeeded for `demo-api-01`.
- Preview changed only `api_instance_type` from `m5.2xlarge` to `m5.xlarge`.
- Terraform `fmt` and `validate` passed inside Docker with the verified provider lock for that platform. No candidate plan was run.
- Exact proposal approval succeeded for `ca45b5ce-bb9f-48d7-a36b-893f2b57792b`.
- Execution returned `PR_CREATED`: https://github.com/Harshavardhan2903/cloudpilot-terraform-demo/pull/2
- The saved dashboard proposal shows `PR_CREATED` and its GitHub link. No merge or infrastructure apply was performed.

Fixes: seed the Terraform fixture and persist its state; mount the GitHub App key read-only; validate with the audited provider lock for the current platform; move workflow registration to Home; prefill the local operator token without embedding it in frontend assets or storing it in browser storage.

Validation: frontend production build passed; 28 execution/hosted tests, one local-session test, and one platform-lock regression test passed.

Screenshots: `execution-home.png` and `terraform-pr-demo.png`.
