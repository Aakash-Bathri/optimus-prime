# Hosted analysis image: no Docker socket, Terraform CLI, Node runtime or lab fixtures.
FROM ghcr.io/astral-sh/uv:0.9.5 AS uv
FROM python:3.12-slim-bookworm
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock backend/
RUN uv sync --directory backend --frozen --no-dev
COPY backend/app backend/app
COPY test-data test-data
ENV PATH="/app/backend/.venv/bin:$PATH" PYTHONPATH=/app/backend PYTHONUNBUFFERED=1 \
    CLOUDPILOT_EXECUTION_ENABLED=false CLOUDPILOT_DATABASE_PATH=/data/cloudpilot.sqlite3
# Bind-mounted persistent data is owned by this unprivileged account.
RUN groupadd --gid 10001 cloudpilot && useradd --uid 10001 --gid 10001 --no-create-home cloudpilot
USER 10001:10001
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
