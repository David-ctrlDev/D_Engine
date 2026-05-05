# dataprep — backend

FastAPI + SQLAlchemy 2.0 (async) + Alembic. Python 3.14, managed by [uv](https://docs.astral.sh/uv/).

## Prerequisites

- Python 3.14 (or let uv install it: `uv python install 3.14`)
- A running Postgres 16 — start it from the repo root with `docker compose up -d`

## Setup

```bash
# from repo root
cd backend

# install deps (creates .venv automatically)
uv sync

# create your local env file and fill in JWT_SECRET / FERNET_KEY
cp .env.example .env

# create the test database (one-time)
docker compose -f ../docker-compose.yml exec postgres \
  createdb -U dataprep dataprep_test

# run migrations
uv run alembic upgrade head

# start the dev server
uv run fastapi dev app/main.py
```

API at <http://localhost:8000>. Swagger UI at <http://localhost:8000/docs>.

## Common commands

```bash
uv run pytest                 # tests
uv run ruff check .           # lint
uv run ruff format .          # autoformat
uv run mypy app               # typecheck
uv run alembic revision -m "<msg>"   # new migration
```

## Layout

```
app/
  main.py            FastAPI factory + lifespan
  config.py          Settings (pydantic-settings)
  logging_config.py  Logger with sensitive-data redaction
  db/                Async engine, session, RLS helpers
  core/              Crypto, JWT, rate limiting, encryption
  auth/              Models, schemas, services, routes
  middleware/        Security headers, tenant context
  utils/             Shared helpers
alembic/             Migrations
tests/               Pytest suite
```

See [`../docs/architecture.md`](../docs/architecture.md) for the bigger picture.
