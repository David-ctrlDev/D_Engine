"""Application settings, loaded from environment variables / `.env`.

All sensitive values (secrets, keys, DSNs) are forced to come from the
environment — there is no in-code default that would let the app start with
guessable credentials.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import AnyHttpUrl, BeforeValidator, Field, SecretStr
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class AppEnv(StrEnum):
    development = "development"
    test = "test"
    production = "production"


class CookieSameSite(StrEnum):
    strict = "strict"
    lax = "lax"
    none = "none"


class RateLimitBackend(StrEnum):
    memory = "memory"
    redis = "redis"


def _split_csv(value: object) -> object:
    """Allow CORS_ORIGINS to be either a list or a comma-separated string."""
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


# NoDecode disables pydantic-settings' default JSON-parse of list/dict fields,
# so the BeforeValidator below sees the raw CSV string from the environment.
CORSOrigins = Annotated[list[AnyHttpUrl], NoDecode, BeforeValidator(_split_csv)]


class Settings(BaseSettings):
    """Strongly-typed settings. Failures here mean the app refuses to start."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ----- App -----
    app_env: AppEnv = AppEnv.development
    log_level: str = "INFO"

    # ----- Database -----
    # We keep DSNs as plain strings because asyncpg-flavoured URLs
    # (postgresql+asyncpg://...) are not always accepted by Pydantic's
    # PostgresDsn, and we already validate the scheme inside the engine factory.
    #
    # Two roles, on purpose:
    #   * ``database_url`` — used at runtime by the app and by tests. Connects
    #     as ``dataprep_app`` (NOSUPERUSER, NOBYPASSRLS) so RLS policies apply.
    #   * ``database_admin_url`` — used by Alembic migrations and by tests for
    #     schema reset / TRUNCATE. Connects as the table owner.
    # Sharing one URL would either skip migrations DDL or, worse, let the
    # runtime bypass RLS — we hit the latter early in development.
    database_url: str = Field(min_length=1)
    database_admin_url: str = Field(min_length=1)
    test_database_url: str = Field(min_length=1)
    test_database_admin_url: str = Field(min_length=1)
    sql_echo: bool = False

    # ----- JWT -----
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_seconds: int = 60 * 15
    jwt_refresh_ttl_seconds: int = 60 * 60 * 24 * 30
    jwt_email_verify_ttl_seconds: int = 60 * 60 * 24
    jwt_password_reset_ttl_seconds: int = 60 * 60
    jwt_mfa_pending_ttl_seconds: int = 60 * 5
    # Short-lived signed state for the OAuth round-trip. 10 min is
    # the standard window — anything shorter and slow consent flows
    # fail; anything longer and we're carrying a CSRF surface for
    # no benefit.
    jwt_oauth_state_ttl_seconds: int = 60 * 10

    # ----- SSO providers -----
    # When the *_id / *_secret pair is unset, the backend treats the
    # provider as "not configured": the /sso/{provider}/start route
    # redirects back to the frontend with ``?sso_error=not_configured``.
    # No code path reads these in plaintext after Settings init — the
    # secret values stay inside ``SecretStr.get_secret_value()`` calls.
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    microsoft_client_id: str | None = None
    microsoft_client_secret: SecretStr | None = None
    # Microsoft tenant id (the directory). "common" allows any work
    # or school account + personal accounts; "organizations" is
    # work/school only. Customers running their own Entra tenant
    # set this to their tenant GUID.
    microsoft_tenant: str = "common"
    # Backend's own public URL — used to build the redirect_uri
    # that the provider calls back to. In dev: http://localhost:8000.
    # In prod: the deployed API origin.
    backend_url: str = "http://localhost:8000"

    # ----- Encryption -----
    fernet_key: SecretStr = Field(min_length=32)

    # ----- Cookies -----
    cookie_secure: bool = False
    cookie_domain: str | None = None
    cookie_samesite: CookieSameSite = CookieSameSite.strict

    # ----- CORS -----
    cors_origins: CORSOrigins = Field(default_factory=list)

    # ----- Frontend -----
    frontend_url: AnyHttpUrl

    # ----- Rate limiting -----
    rate_limit_backend: RateLimitBackend = RateLimitBackend.memory
    redis_url: str = "redis://localhost:6379/0"

    # ----- Local file storage -----
    # Where uploaded files (csv/parquet/xlsx) live. Per-tenant subtree, owned
    # by the OS user the app runs as. We deliberately store files under a
    # per-tenant directory so a path traversal bug can't escape the
    # workspace it was uploaded from. S3 / Azure Blob is a future swap-in
    # behind the same ``LocalFileStorage`` interface.
    file_storage_root: str = "./var/uploads"
    # Hard cap on a single upload. 500 MiB is generous for a CSV/parquet/xlsx
    # while still preventing DoS via /dev/zero-style payloads.
    file_upload_max_bytes: int = 500 * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.app_env is AppEnv.production


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached accessor. Tests can clear the cache via `get_settings.cache_clear()`."""
    return Settings()


settings = get_settings()
