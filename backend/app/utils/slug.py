"""Slug utilities for tenant URL identifiers.

A slug is the URL-safe, lowercase, hyphenated form of a workspace name. We
keep it stable (immutable after creation) so links don't rot.

The slugify rules are deliberately conservative:

* ASCII-fold via :func:`unicodedata.normalize` so accents collapse
  ("Café Acmé" → "cafe-acme").
* Replace any non-alphanumeric with a single hyphen.
* Collapse repeated hyphens, trim leading/trailing hyphens.
* Lowercase.

Length is bounded by ``MAX_SLUG_LENGTH``. Collision-resolution happens at
the call site by appending an 8-character random suffix.
"""

from __future__ import annotations

import re
import secrets
import unicodedata

MAX_SLUG_LENGTH = 60
COLLISION_SUFFIX_LENGTH = 8

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_LEADING_TRAILING_HYPHEN = re.compile(r"(^-+|-+$)")
_REPEATED_HYPHEN = re.compile(r"-{2,}")


def slugify(text: str) -> str:
    """Return a URL-safe slug for ``text``. May be empty if input has no
    alphanumeric characters; callers must handle that case (e.g. fall back
    to a random slug)."""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = _NON_ALNUM.sub("-", folded.lower())
    slug = _REPEATED_HYPHEN.sub("-", slug)
    slug = _LEADING_TRAILING_HYPHEN.sub("", slug)
    return slug[:MAX_SLUG_LENGTH]


def slug_with_random_suffix(base: str) -> str:
    """Append a random suffix so a colliding base slug becomes unique.

    Used by the registration service when ``slugify(workspace_name)``
    already exists on another tenant.
    """
    suffix = secrets.token_hex(COLLISION_SUFFIX_LENGTH // 2)
    truncated = base[: MAX_SLUG_LENGTH - COLLISION_SUFFIX_LENGTH - 1]
    return f"{truncated}-{suffix}" if truncated else suffix
