"""Request and response schemas for /api/v1/auth/*.

Conventions:

* Request models forbid extra fields so a typo in the frontend surfaces
  as a 422, not a silently-ignored attribute.
* Response models are minimal — they expose the smallest API surface that
  the frontend needs, and never include hashed passwords / token hashes /
  TOTP secrets.
"""

# Note: ``from __future__ import annotations`` is intentionally omitted.
# Pydantic v2 evaluates field type annotations at class-creation time, so
# every name used as an annotation (datetime, UUID, EmailStr, TenantRole)
# must be importable at runtime, not just under TYPE_CHECKING.
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.auth.models import TenantRole

# ---------------------------------------------------------------------------
# Common
# ---------------------------------------------------------------------------


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------


class RegisterRequest(_StrictModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=200)
    workspace_name: str = Field(min_length=1, max_length=120)


class RegisterResponse(BaseModel):
    user_id: UUID
    tenant_id: UUID
    tenant_slug: str
    message: str = "Account created. Check your email to verify."


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------


class VerifyEmailRequest(_StrictModel):
    token: str = Field(min_length=1)


class VerifyEmailResponse(BaseModel):
    user_id: UUID
    verified: bool = True


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


class LoginRequest(_StrictModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserPublic(BaseModel):
    """Public projection of a User used in /auth/me + login responses."""

    id: UUID
    email: EmailStr
    is_verified: bool


class TenantPublic(BaseModel):
    id: UUID
    slug: str
    name: str
    role: TenantRole


class LoginSuccessResponse(BaseModel):
    user: UserPublic
    tenant: TenantPublic
    mfa_required: bool = False


class LoginMFARequiredResponse(BaseModel):
    mfa_required: bool = True
    mfa_token: str


# ---------------------------------------------------------------------------
# MFA verify (second leg of /auth/login when MFA is on)
# ---------------------------------------------------------------------------


class MFAVerifyRequest(_StrictModel):
    mfa_token: str = Field(min_length=1)
    code: str = Field(min_length=1, max_length=64)


# ---------------------------------------------------------------------------
# MFA setup
# ---------------------------------------------------------------------------


class MFASetupResponse(BaseModel):
    secret: str
    qr_data_uri: str


class MFAConfirmRequest(_StrictModel):
    code: str = Field(min_length=6, max_length=6)


class MFAConfirmResponse(BaseModel):
    recovery_codes: list[str]
    message: str = "Save these recovery codes somewhere safe. They are shown once."


class MFADisableRequest(_StrictModel):
    password: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=6, max_length=6)


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------


class ForgotPasswordRequest(_StrictModel):
    email: EmailStr


class ResetPasswordRequest(_StrictModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=12, max_length=200)


# ---------------------------------------------------------------------------
# Sessions / logout
# ---------------------------------------------------------------------------


class SessionInfo(BaseModel):
    id: UUID
    created_at: datetime
    expires_at: datetime
    user_agent: str | None
    ip: str | None
    is_current: bool = False


class SessionListResponse(BaseModel):
    sessions: list[SessionInfo]


# ---------------------------------------------------------------------------
# Generic ack
# ---------------------------------------------------------------------------


class MessageResponse(BaseModel):
    message: str
