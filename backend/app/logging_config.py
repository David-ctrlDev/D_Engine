"""Logging configuration with explicit redaction of sensitive fields.

The first line of defence is discipline: never log a password, token, or
secret. This module is the second line of defence. It installs a filter
that redacts known sensitive keys whenever they appear in:

  * keyword arguments passed to a logging call (``extra=`` payload)
  * ``args`` mapping (``logger.info("%(password)s", {"password": ...})``)
  * inline ``key=value`` substrings inside the formatted message

Anything matching the ``SENSITIVE_KEYS`` set is replaced with ``***``.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from logging.config import dictConfig
from typing import Any

from app.config import settings

REDACTED = "***"

# Lowercased keys whose values must never appear in logs.
SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "new_password",
        "old_password",
        "current_password",
        "hashed_password",
        "secret",
        "client_secret",
        "totp_secret",
        "fernet_key",
        "jwt_secret",
        "token",
        "access_token",
        "refresh_token",
        "mfa_token",
        "id_token",
        "authorization",
        "cookie",
        "set_cookie",
        "code",
        "totp_code",
        "recovery_code",
        "recovery_codes",
        "verification_code",
        "reset_token",
        "verify_token",
        "session_token",
    }
)

# Catches "password=abc", "token: xyz", "Bearer eyJ..." inside a single string.
_INLINE_PATTERN = re.compile(
    r"(?P<key>"
    + "|".join(re.escape(k) for k in sorted(SENSITIVE_KEYS, key=len, reverse=True))
    + r")(?P<sep>\s*[:=]\s*|\s+)(?P<val>[^\s,;]+)",
    re.IGNORECASE,
)
_BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]+")


def _redact_mapping(data: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(key, str) and key.lower() in SENSITIVE_KEYS:
            out[key] = REDACTED
        elif isinstance(value, Mapping):
            out[key] = _redact_mapping(value)
        else:
            out[key] = value
    return out


def _redact_string(message: str) -> str:
    message = _INLINE_PATTERN.sub(lambda m: f"{m.group('key')}{m.group('sep')}{REDACTED}", message)
    message = _BEARER_PATTERN.sub("Bearer " + REDACTED, message)
    return message


class SensitiveDataFilter(logging.Filter):
    """Logging filter that redacts known sensitive fields.

    Acts on both structured ``args``/``extra`` (preferred) and on the final
    formatted string (best-effort).
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, Mapping):
            record.args = _redact_mapping(record.args)
        for attr in list(vars(record)):
            if attr.lower() in SENSITIVE_KEYS:
                setattr(record, attr, REDACTED)
        if isinstance(record.msg, str):
            record.msg = _redact_string(record.msg)
        return True


def configure_logging() -> None:
    """Install root logger configuration with the sensitive-data filter."""
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "redact_sensitive": {"()": SensitiveDataFilter},
            },
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)-8s %(name)s :: %(message)s",
                    "datefmt": "%Y-%m-%dT%H:%M:%S%z",
                },
            },
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "filters": ["redact_sensitive"],
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "level": settings.log_level.upper(),
                "handlers": ["stdout"],
            },
            "loggers": {
                "uvicorn": {"level": settings.log_level.upper(), "propagate": True},
                "uvicorn.error": {"level": settings.log_level.upper(), "propagate": True},
                "uvicorn.access": {"level": settings.log_level.upper(), "propagate": True},
                "sqlalchemy.engine": {
                    "level": "INFO" if settings.sql_echo else "WARNING",
                    "propagate": True,
                },
            },
        }
    )
