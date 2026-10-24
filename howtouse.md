# How to use CloudPilot

1. Follow the README setup. Start Docker Engine to use LocalStack.
2. Start the backend on port 8001 and frontend on port 5173.
3. Open http://localhost:5173 and choose **Use demo profile**.
4. Open **Recommendations** and inspect a resize finding.
5. Click **Queue for review**, then **Open in execution lab**.
6. Enter your local operator token from `.env`. Connect and register the demo resources.
7. Load the candidate evidence and choose a supported CPU/RAM size.
8. Choose the manual destination for LocalStack, or Terraform for a GitHub PR.
9. Prepare the preview, read it, approve it, then click the separate execute button.
10. Check **APPLIED** or **PR_CREATED**, the verified result and audit history.
11. Use **Prepare inverse change** to review and approve a manual restore.

The dataset is historical. Lab tests do not change real Utho resources or prove savings.
A Terraform PR changes infrastructure after the customer merges and applies it.
