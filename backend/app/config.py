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
from pydantic_settings import BaseSettings, SettingsConfigDict


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


CORSOrigins = Annotated[list[AnyHttpUrl], BeforeValidator(_split_csv)]


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
    database_url: str = Field(min_length=1)
    test_database_url: str = Field(min_length=1)
    sql_echo: bool = False

    # ----- JWT -----
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_seconds: int = 60 * 15
    jwt_refresh_ttl_seconds: int = 60 * 60 * 24 * 30
    jwt_email_verify_ttl_seconds: int = 60 * 60 * 24
    jwt_password_reset_ttl_seconds: int = 60 * 60
    jwt_mfa_pending_ttl_seconds: int = 60 * 5

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

    @property
    def is_production(self) -> bool:
        return self.app_env is AppEnv.production


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached accessor. Tests can clear the cache via `get_settings.cache_clear()`."""
    return Settings()


settings = get_settings()
