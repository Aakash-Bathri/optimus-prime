# CloudPilot

Built for a hackathon, CloudPilot helps teams spot cloud waste, review cost-saving recommendations, and explore what-if scenarios using synthetic resource and usage data. Its execution lab supports approved LocalStack changes and Terraform pull requests.

**Tech stack:** React 19, TypeScript, Vite, Tailwind CSS, Python 3.12+, FastAPI, SQLite, Docker, LocalStack, and Terraform. Optional LLM and GitHub App integrations power explanations and pull requests.

## Local setup / quick start

Install Python 3.12+, [uv](https://docs.astral.sh/uv/), and Node.js 22.12+.

```sh
uv sync --directory backend
npm --prefix frontend ci
uv run --directory backend uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

In a second terminal:

```sh
npm --prefix frontend run dev
```

Open [localhost:5173](http://localhost:5173); API docs are at [localhost:8001/docs](http://localhost:8001/docs). Basic analysis works without cloud credentials. For optional LLM, LocalStack, or GitHub integrations, use `.env.example` as a configuration reference.

CloudPilot makes potential savings and capacity tradeoffs easier to review before changing infrastructure. Results use synthetic data; LocalStack changes demonstrate the workflow rather than production savings.
