# dataprep

Multi-tenant SaaS platform for data preparation. This repository currently
contains the project scaffold and the authentication system; the data
ingestion / profiling / cleaning core will land in subsequent iterations.

## Repository layout

```
backend/   FastAPI + SQLAlchemy 2.0 (async) + Alembic
frontend/  Next.js 14 (App Router) + TypeScript + Tailwind + shadcn/ui
docs/      Architecture overview, threat model, ADRs
```

## Quickstart

You will need: Python 3.14, Node 20+, [pnpm](https://pnpm.io),
[uv](https://docs.astral.sh/uv/), and Docker Desktop.

```bash
# 1. Start Postgres (and Redis, declared but unused in v0)
docker compose up -d

# 2. Backend
cd backend && uv sync && uv run alembic upgrade head && uv run fastapi dev

# 3. Frontend (in a second terminal)
cd frontend && pnpm install && pnpm dev
```

Backend at <http://localhost:8000>, frontend at <http://localhost:3000>.
Per-package READMEs cover details:
[`backend/README.md`](./backend/README.md), [`frontend/README.md`](./frontend/README.md).

## Documentation

- [`docs/architecture.md`](./docs/architecture.md) — system overview
- [`docs/security.md`](./docs/security.md) — threat model
- [`docs/adr/`](./docs/adr/) — architecture decision records

## Status

v0 — authentication only. The data preparation engine has not been built yet.
