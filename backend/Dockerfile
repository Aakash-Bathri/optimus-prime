FROM node:22-bookworm-slim AS node
FROM ghcr.io/astral-sh/uv:0.9.5 AS uv
FROM hashicorp/terraform:1.10.5 AS terraform
FROM python:3.12-slim-bookworm
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm
COPY --from=uv /uv /usr/local/bin/uv
COPY --from=terraform /bin/terraform /usr/local/bin/terraform
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock backend/
RUN uv sync --directory backend --frozen --no-dev
COPY infra/localstack-mcp/package*.json infra/localstack-mcp/
RUN npm --prefix infra/localstack-mcp ci --omit=dev
COPY backend/app backend/app
COPY infra/demo-terraform infra/demo-terraform
RUN terraform -chdir=infra/demo-terraform init -backend=false -input=false
COPY infra/seed_manual_demo.py infra/seed_terraform_demo.py infra/
COPY test-data test-data
ENV PATH="/app/backend/.venv/bin:$PATH" PYTHONPATH=/app/backend PYTHONUNBUFFERED=1
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
