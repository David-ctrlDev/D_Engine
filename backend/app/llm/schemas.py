"""Pydantic schemas for /api/v1/llm-credentials.

Conventions mirror :mod:`app.auth.schemas` and
:mod:`app.data.schemas`:

* request bodies forbid extra fields,
* responses never echo ``api_key`` — even on the test endpoint
  the body returns ``ok / error``, not the key,
* enum values come straight from the SQLAlchemy enums.

``from __future__ import annotations`` is intentionally *omitted*:
Pydantic v2 evaluates annotations at class-creation time.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.llm.models import LlmMemberAccess, LlmProviderKind


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------------------------------------------------------------------------
# Provider catalogue (read-only, for the new-credential form)
# ---------------------------------------------------------------------------


class ModelOptionPublic(BaseModel):
    id: str
    label: str
    notes: str | None


class ProviderInfoPublic(BaseModel):
    kind: LlmProviderKind
    display_name: str
    description: str
    api_key_docs_url: str
    needs_base_url: bool
    default_model: str
    models: list[ModelOptionPublic]


class ProvidersResponse(BaseModel):
    providers: list[ProviderInfoPublic]


# ---------------------------------------------------------------------------
# Credentials — public projection (no api_key)
# ---------------------------------------------------------------------------


class LlmCredentialPublic(BaseModel):
    """Public projection — everything the UI needs to render a
    credential row, minus the encrypted secret."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider: LlmProviderKind
    nickname: str
    model_default: str | None
    base_url: str | None
    member_access: LlmMemberAccess
    last_tested_at: datetime | None
    last_test_status: str | None
    last_test_error: str | None
    created_at: datetime


class LlmCredentialListResponse(BaseModel):
    credentials: list[LlmCredentialPublic]


# ---------------------------------------------------------------------------
# Create / update
# ---------------------------------------------------------------------------


class LlmCredentialCreateRequest(_StrictModel):
    provider: LlmProviderKind
    nickname: str = Field(min_length=1, max_length=120)
    api_key: str = Field(min_length=1, max_length=500)
    model_default: str | None = Field(default=None, max_length=120)
    base_url: str | None = Field(default=None, max_length=255)
    member_access: LlmMemberAccess = LlmMemberAccess.admins_only


class LlmCredentialUpdateRequest(_StrictModel):
    """All fields optional — only those provided are touched. The
    ``api_key`` field is the only way to rotate the secret; an
    explicit ``null`` doesn't blank it (would be ambiguous), an
    omitted field leaves the key alone."""

    nickname: str | None = Field(default=None, min_length=1, max_length=120)
    api_key: str | None = Field(default=None, min_length=1, max_length=500)
    model_default: str | None = Field(default=None, max_length=120)
    base_url: str | None = Field(default=None, max_length=255)
    member_access: LlmMemberAccess | None = None


# ---------------------------------------------------------------------------
# Test connection
# ---------------------------------------------------------------------------


class TestConnectionRequest(_StrictModel):
    """Test an *unsaved* credential — used by the new-credential
    form before the admin clicks Save. Used credentials test via
    the persisted-credential endpoint that takes no body."""

    provider: LlmProviderKind
    api_key: str = Field(min_length=1, max_length=500)
    base_url: str | None = Field(default=None, max_length=255)


class TestConnectionResponse(BaseModel):
    ok: bool
    error: str | None = None
    # Live model list parsed from the provider's ``/models`` response.
    # Empty when the probe failed; the UI falls back to the curated static
    # catalogue in that case.
    models: list[ModelOptionPublic] = []


# ---------------------------------------------------------------------------
# Grants
# ---------------------------------------------------------------------------


class GrantUserRequest(_StrictModel):
    user_id: UUID


class LlmCredentialGrantPublic(BaseModel):
    id: UUID
    user_id: UUID
    user_email: str
    granted_at: datetime


class LlmCredentialGrantsResponse(BaseModel):
    grants: list[LlmCredentialGrantPublic]


__all__ = [
    "GrantUserRequest",
    "LlmCredentialCreateRequest",
    "LlmCredentialGrantPublic",
    "LlmCredentialGrantsResponse",
    "LlmCredentialListResponse",
    "LlmCredentialPublic",
    "LlmCredentialUpdateRequest",
    "ModelOptionPublic",
    "ProviderInfoPublic",
    "ProvidersResponse",
    "TestConnectionRequest",
    "TestConnectionResponse",
]
