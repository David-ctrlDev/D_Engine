"""Cookie naming and helpers.

Two cookies, both ``HttpOnly``:

* ``ACCESS_COOKIE_NAME`` — short-lived JWT, sent on every API call.
* ``REFRESH_COOKIE_NAME`` — long-lived opaque token. ``Path`` is restricted
  to the refresh endpoint so the browser doesn't send it with normal API
  traffic; that way a CSRF that managed to issue a request to ``/api/v1/...``
  cannot also acquire a fresh access token.

Cookie attributes are read from ``settings`` so dev (``Secure=false``,
empty ``Domain``) and prod (``Secure=true``, real domain) share the code.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from fastapi import Response

ACCESS_COOKIE_NAME = "dataprep_access"
REFRESH_COOKIE_NAME = "dataprep_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"  # refresh + logout both live under here


def _common_kwargs() -> dict[str, object]:
    return {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite.value,
        "domain": settings.cookie_domain or None,
    }


def set_access_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=token,
        max_age=settings.jwt_access_ttl_seconds,
        path="/",
        **_common_kwargs(),  # type: ignore[arg-type]
    )


def set_refresh_cookie(response: Response, token: str, expires_at: datetime) -> None:
    max_age = max(int((expires_at - datetime.now(UTC)).total_seconds()), 0)
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=max_age,
        path=REFRESH_COOKIE_PATH,
        **_common_kwargs(),  # type: ignore[arg-type]
    )


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(
        key=ACCESS_COOKIE_NAME,
        path="/",
        domain=settings.cookie_domain or None,
    )
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        domain=settings.cookie_domain or None,
    )
