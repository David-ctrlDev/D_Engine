"""Recovery code generation and verification.

Format
------

Codes are produced as three groups of four upper-case alphanumeric
characters joined by ``-``: ``XXXX-XXXX-XXXX``. The hyphens are cosmetic;
they make the codes easier to read but are stripped before hashing so
users may type them with or without separators.

Entropy
-------

Each character comes from a 32-symbol alphabet (Crockford-base32 minus
similar-looking characters). 12 characters give ~60 bits — strong enough
for a single-use code, especially given:

* the verification endpoint is rate-limited;
* a successful attempt invalidates the code (``used_at`` is set);
* per-user codes are bcrypt-hashed at rest, so a DB dump still costs
  the attacker per-guess work.
"""

from __future__ import annotations

import secrets

# Crockford-base32 minus 0/O and 1/I/L to avoid transcription errors.
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"
GROUP_LENGTH = 4
GROUP_COUNT = 3
TOTAL_CODES = 10


def _generate_one() -> str:
    raw = "".join(secrets.choice(_ALPHABET) for _ in range(GROUP_LENGTH * GROUP_COUNT))
    return "-".join(raw[i : i + GROUP_LENGTH] for i in range(0, len(raw), GROUP_LENGTH))


def generate_recovery_codes(count: int = TOTAL_CODES) -> list[str]:
    """Return ``count`` (default 10) cleartext recovery codes."""
    return [_generate_one() for _ in range(count)]


def normalize(code: str) -> str:
    """Strip whitespace and hyphens, upper-case. Use before hashing /
    comparing so a user typing ``abcd efgh 1234`` matches stored
    ``ABCD-EFGH-1234``."""
    return code.replace("-", "").replace(" ", "").upper().strip()
