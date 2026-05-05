-- Initialise the runtime application role.
--
-- The role created by POSTGRES_USER (``dataprep``) is a SUPERUSER and is the
-- owner of every table the migrations create. SUPERUSERS bypass Row-Level
-- Security unconditionally, even with FORCE RLS — so we cannot use it for
-- tenant-scoped queries: tests and production traffic must connect as a
-- regular role.
--
-- This script runs once when the data volume is first initialised (Postgres
-- only executes ``/docker-entrypoint-initdb.d/*`` on a fresh cluster). To
-- re-run it, recreate the volume:
--
--     docker compose down -v
--     docker compose up -d
--
-- The migration in alembic/versions/0001_*.py is responsible for granting
-- per-table privileges to ``dataprep_app`` after the schema is created.

CREATE ROLE dataprep_app
    LOGIN
    PASSWORD 'dataprep_app_dev'
    NOSUPERUSER
    NOBYPASSRLS
    INHERIT;

GRANT CONNECT ON DATABASE dataprep TO dataprep_app;
