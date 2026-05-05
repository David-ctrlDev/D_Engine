"""Tests for app.auth.passwords."""

from __future__ import annotations

import pytest
from app.auth.passwords import (
    MIN_PASSWORD_LENGTH,
    WeakPasswordError,
    validate_password_strength,
)


class TestLengthCheck:
    def test_too_short_password_rejected(self) -> None:
        with pytest.raises(WeakPasswordError) as excinfo:
            validate_password_strength("a" * (MIN_PASSWORD_LENGTH - 1))
        assert "at least" in str(excinfo.value).lower()

    def test_minimum_length_alone_is_not_enough(self) -> None:
        """A password long enough but weak (e.g. 'aaaaaaaaaaaa') should
        still be rejected by zxcvbn even though it passes the length check."""
        with pytest.raises(WeakPasswordError):
            validate_password_strength("a" * MIN_PASSWORD_LENGTH)


class TestStrengthCheck:
    def test_extremely_common_password_rejected(self) -> None:
        with pytest.raises(WeakPasswordError):
            # Top 10 worst password lists hit this directly
            validate_password_strength("password1234")

    def test_obvious_keyboard_pattern_rejected(self) -> None:
        with pytest.raises(WeakPasswordError):
            validate_password_strength("qwertyuiopasd")

    def test_strong_random_passphrase_accepted(self) -> None:
        # Four random uncommon words → very high zxcvbn score
        validate_password_strength("velvet harbor pumice galaxy")

    def test_strong_mixed_password_accepted(self) -> None:
        validate_password_strength("J7#zx!ptVqA9w")

    def test_user_inputs_penalise_passwords_built_around_them(self) -> None:
        """A password that is essentially the user's email shouldn't pass:
        zxcvbn must take ``user_inputs`` into account even if the candidate
        is otherwise long enough to look entropic."""
        email = "alice.smith@acme.test"
        # Same string as the email — without user_inputs zxcvbn would treat
        # this as a long unique string. With user_inputs it's guessable
        # immediately by anyone who knows the email.
        candidate = "alice.smith@acme.test"
        with pytest.raises(WeakPasswordError):
            validate_password_strength(candidate, user_inputs=[email])


class TestErrorPayload:
    def test_weak_password_error_carries_suggestions(self) -> None:
        try:
            validate_password_strength("password1234")
        except WeakPasswordError as exc:
            assert isinstance(exc.suggestions, list)
        else:
            pytest.fail("expected WeakPasswordError")
