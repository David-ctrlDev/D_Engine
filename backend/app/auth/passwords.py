"""Password strength validation.

Two checks, in order of cheapness:

1. **Length** ≥ 12 characters.
2. **zxcvbn score** ≥ 3 ("safely unguessable: moderate protection from
   offline slow-hash scenario") on a 0-4 scale. zxcvbn already covers the
   "list of 10k worst passwords" requirement implicitly — its dictionary
   is far broader than that.

The function accepts ``user_inputs`` (e.g. the user's email and tenant
name) so zxcvbn can flag passwords that are mostly composed of
personally-identifiable values, which would otherwise score artificially
high on entropy alone.
"""

from __future__ import annotations

from zxcvbn import zxcvbn

MIN_PASSWORD_LENGTH = 12
MIN_ZXCVBN_SCORE = 3


class WeakPasswordError(ValueError):
    """Raised when a candidate password fails strength validation.

    The endpoint layer maps this to HTTP 422 with structured feedback so
    the frontend can display targeted help.
    """

    def __init__(self, message: str, *, suggestions: list[str] | None = None) -> None:
        super().__init__(message)
        self.suggestions: list[str] = suggestions or []


def validate_password_strength(password: str, *, user_inputs: list[str] | None = None) -> None:
    """Raise :class:`WeakPasswordError` if the password is unacceptable.

    ``user_inputs`` should include any user-known strings (email, name,
    workspace) so zxcvbn penalises passwords built around them.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.")

    result = zxcvbn(password, user_inputs=user_inputs or [])
    score = int(result["score"])
    if score < MIN_ZXCVBN_SCORE:
        feedback = result.get("feedback", {}) or {}
        warning = (feedback.get("warning") or "").strip()
        suggestions = list(feedback.get("suggestions") or [])
        message = warning or "Password is too weak; choose a stronger one."
        raise WeakPasswordError(message, suggestions=suggestions)
