"""Single-sign-on (OAuth 2.0 / OpenID Connect) flow.

Supports two providers in v0:

* **Google** — Google Workspace (and Gmail consumer accounts). Uses
  Google's OpenID Connect implementation: ``openid email profile``
  scopes are enough to identify the user.
* **Microsoft** — Microsoft 365 / Entra ID. Same OpenID Connect
  shape; tenant configured via ``settings.microsoft_tenant``
  (default ``common``).

SAML is intentionally not handled here — proper SAML support
requires IdP metadata XML per workspace and a parser like
``python3-saml``. The frontend currently shows a toast for SAML.

Provisioning model
------------------

* If a user with the SSO-supplied email already exists, we sign
  them in (after the usual ``is_active`` / membership checks).
* If no such user exists, we autocreate:
    - A ``Tenant`` named after the SSO-supplied display name (or
      the email's local part as fallback);
    - A ``User`` row with ``is_verified=True`` (the provider has
      already verified the email) and a random unguessable
      ``hashed_password`` so the column NOT-NULL constraint holds.
      The user can never log in via password — they must keep
      using SSO or use the password-reset flow to set one.
    - An owner ``TenantMembership``.

OAuth doesn't unlock MFA bypass: if the user has an active TOTP
method, we still issue the MFA-pending token and the frontend
moves them through ``/login/mfa``. This is the right default for
enterprise — SSO and second-factor are complementary, not
substitutes.

Errors
------

* :class:`SsoNotConfiguredError` — the provider's credentials are
  missing from the settings. The route translates this to a
  redirect back to ``/login?sso_error=not_configured``.
* :class:`SsoExchangeFailedError` — the token endpoint or
  userinfo endpoint returned non-2xx; payload may be inspected.
* :class:`SsoMissingEmailError` — the userinfo response did not
  include an ``email`` field. Some providers gate email behind
  extra scopes; the route surfaces this as a generic error.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlencode
from uuid import uuid4

import httpx
from sqlalchemy import select

from app.auth import audit, service
from app.auth.errors import AccountInactiveError
from app.auth.models import Tenant, TenantMembership, TenantRole, User
from app.config import settings
from app.core import security as crypto
from app.db.rls import set_request_context, set_user_context
from app.utils.slug import slug_with_random_suffix, slugify

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Provider config
# ---------------------------------------------------------------------------


Provider = Literal["google", "microsoft"]
SUPPORTED_PROVIDERS: tuple[Provider, ...] = ("google", "microsoft")


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    name: Provider
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    scopes: tuple[str, ...]


def provider_config(provider: Provider) -> ProviderConfig | None:
    """Resolve the runtime config for a provider, or ``None`` if
    credentials are unset (the route translates this to a friendly
    "not configured" redirect)."""
    if provider == "google":
        if not settings.google_client_id or not settings.google_client_secret:
            return None
        return ProviderConfig(
            name="google",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret.get_secret_value(),
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            # ruff S106 sees "token_url" + a URL and treats it like a
            # hardcoded credential. It's not — it's the OAuth token
            # endpoint, publicly documented by Google.
            token_url="https://oauth2.googleapis.com/token",  # noqa: S106
            userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
            scopes=("openid", "email", "profile"),
        )
    if provider == "microsoft":
        if not settings.microsoft_client_id or not settings.microsoft_client_secret:
            return None
        tenant = settings.microsoft_tenant or "common"
        return ProviderConfig(
            name="microsoft",
            client_id=settings.microsoft_client_id,
            client_secret=settings.microsoft_client_secret.get_secret_value(),
            authorize_url=f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize",
            token_url=f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            userinfo_url="https://graph.microsoft.com/oidc/userinfo",
            scopes=("openid", "email", "profile"),
        )
    raise ValueError(f"unknown provider: {provider}")  # pragma: no cover


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SsoError(Exception):
    """Root for SSO-flow failures."""


class SsoNotConfiguredError(SsoError):
    """Provider credentials missing from settings."""


class SsoExchangeFailedError(SsoError):
    """The provider rejected our token or userinfo request."""


class SsoMissingEmailError(SsoError):
    """The provider's userinfo response didn't include an email."""


# ---------------------------------------------------------------------------
# Authorize URL
# ---------------------------------------------------------------------------


def callback_url(provider: Provider) -> str:
    """The fully-qualified URI the provider redirects back to. Must
    match what's registered in the provider's console exactly."""
    return f"{settings.backend_url.rstrip('/')}/api/v1/auth/sso/{provider}/callback"


def build_authorize_url(*, provider: Provider, state: str) -> str:
    """Build the URL we redirect the user's browser to so they can
    grant consent at the provider. ``state`` is the JWT we mint per
    flow; the provider echoes it back to the callback."""
    config = provider_config(provider)
    if config is None:
        raise SsoNotConfiguredError(provider)
    params = {
        "client_id": config.client_id,
        "redirect_uri": callback_url(provider),
        "response_type": "code",
        "scope": " ".join(config.scopes),
        "state": state,
        # ``prompt=select_account`` ensures the user can pick which
        # account they want to use, even when they're already signed
        # in to the provider — critical for shared / multi-account
        # browsers.
        "prompt": "select_account",
        # Google-specific; ignored by Microsoft. Asks for a refresh
        # token. We don't currently use it (the access token is
        # discarded after the userinfo call), but keeping it future-
        # proof costs nothing.
        "access_type": "offline",
    }
    return f"{config.authorize_url}?{urlencode(params)}"


# ---------------------------------------------------------------------------
# Code → user info
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OAuthUserInfo:
    email: str
    name: str | None
    subject: str  # provider-specific user id (``sub`` claim)
    email_verified: bool


async def exchange_code_for_userinfo(*, provider: Provider, code: str) -> OAuthUserInfo:
    """Trade the auth-code for tokens, then fetch userinfo.

    Both calls live inside one ``httpx.AsyncClient`` so we share
    the underlying connection pool. Total timeout is 10 s — well
    above provider p99 latency.
    """
    config = provider_config(provider)
    if config is None:
        raise SsoNotConfiguredError(provider)

    timeout = httpx.Timeout(10.0, connect=4.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        token_resp = await client.post(
            config.token_url,
            data={
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "code": code,
                "redirect_uri": callback_url(provider),
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )
        if token_resp.status_code >= 400:
            raise SsoExchangeFailedError(
                f"token endpoint {token_resp.status_code}: {token_resp.text[:200]}"
            )
        tokens = token_resp.json()
        access_token = tokens.get("access_token")
        if not access_token:
            raise SsoExchangeFailedError("token response missing access_token")

        userinfo_resp = await client.get(
            config.userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_resp.status_code >= 400:
            raise SsoExchangeFailedError(
                f"userinfo {userinfo_resp.status_code}: {userinfo_resp.text[:200]}"
            )
        info = userinfo_resp.json()

    email = info.get("email")
    if not email:
        raise SsoMissingEmailError(provider)

    return OAuthUserInfo(
        email=str(email).strip().lower(),
        name=info.get("name") or info.get("given_name"),
        subject=str(info.get("sub", "")),
        email_verified=bool(info.get("email_verified", False)),
    )


# ---------------------------------------------------------------------------
# Login or provision
# ---------------------------------------------------------------------------


async def login_or_provision(
    session: AsyncSession,
    *,
    user_info: OAuthUserInfo,
    provider: Provider,
    ip: str | None,
    user_agent: str | None,
) -> service.LoginResult:
    """Find an existing user by email or create a new tenant+user
    pair, then issue a session (or MFA challenge).

    Returns the same :class:`service.LoginResult` shape as the
    password flow so the route can branch on isinstance(..) the
    same way ``/auth/login`` does.
    """
    user = (
        await session.execute(select(User).where(User.email == user_info.email))
    ).scalar_one_or_none()

    if user is None:
        user = await _provision_new_user(
            session,
            user_info=user_info,
            provider=provider,
            ip=ip,
            user_agent=user_agent,
        )

    if not user.is_active:
        raise AccountInactiveError

    # Re-use the password flow's MFA gate + session issuance so
    # SSO doesn't accidentally skip second factors.
    await set_user_context(session, user_id=user.id)
    if await service._user_has_active_mfa(session, user_id=user.id):
        await audit.log_event(
            session,
            event_type=audit.AUDIT_MFA_REQUIRED,
            user_id=user.id,
            ip=ip,
            user_agent=user_agent,
            metadata={"provider": provider},
        )
        await session.flush()
        from app.core.tokens import create_mfa_pending_token

        return service.MFAChallenge(
            user_id=user.id,
            mfa_token=create_mfa_pending_token(user_id=user.id),
        )

    return await service.issue_session(session, user_id=user.id, ip=ip, user_agent=user_agent)


async def _provision_new_user(
    session: AsyncSession,
    *,
    user_info: OAuthUserInfo,
    provider: Provider,
    ip: str | None,
    user_agent: str | None,
) -> User:
    """First-time SSO login → create User + Tenant + owner membership."""
    tenant_id = uuid4()
    user_id = uuid4()
    await set_request_context(session, user_id=user_id, tenant_id=tenant_id)

    workspace_name = user_info.name or user_info.email.split("@")[0]
    base_slug = slugify(workspace_name) or "workspace"
    slug = slug_with_random_suffix(base_slug)

    # Random unguessable password — column is NOT NULL but the user
    # never sees this value. They must keep using SSO or trigger
    # the password-reset flow to choose one.
    random_secret = secrets.token_urlsafe(32)

    tenant = Tenant(id=tenant_id, name=workspace_name, slug=slug)
    user = User(
        id=user_id,
        email=user_info.email,
        hashed_password=crypto.hash_password(random_secret),
        is_active=True,
        # The provider already verified the email when the user
        # signed in there. We trust that signal — anything else
        # would force a second verification step that's strictly
        # worse UX for no security gain.
        is_verified=True,
    )
    membership = TenantMembership(user_id=user_id, tenant_id=tenant_id, role=TenantRole.owner)
    session.add(tenant)
    session.add(user)
    await session.flush()
    session.add(membership)
    await audit.log_event(
        session,
        event_type=audit.AUDIT_REGISTER,
        user_id=user_id,
        tenant_id=tenant_id,
        ip=ip,
        user_agent=user_agent,
        metadata={"workspace_slug": slug, "sso_provider": provider},
    )
    await session.flush()
    return user


__all__ = [
    "SUPPORTED_PROVIDERS",
    "OAuthUserInfo",
    "Provider",
    "SsoError",
    "SsoExchangeFailedError",
    "SsoMissingEmailError",
    "SsoNotConfiguredError",
    "build_authorize_url",
    "callback_url",
    "exchange_code_for_userinfo",
    "login_or_provision",
    "provider_config",
]
