"""Tests for app.auth.email."""

from __future__ import annotations

import pytest
from app.auth.email import CapturingEmailSender, ConsoleEmailSender, EmailMessage


async def test_console_sender_writes_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    sender = ConsoleEmailSender()
    await sender.send(
        EmailMessage(
            to="alice@acme.test",
            subject="Verify your email",
            text_body="Click here: https://example/verify?token=abc",
        )
    )
    captured = capsys.readouterr()
    assert "alice@acme.test" in captured.out
    assert "Verify your email" in captured.out
    assert "https://example/verify?token=abc" in captured.out


async def test_capturing_sender_collects_messages_in_order() -> None:
    sender = CapturingEmailSender()
    first = EmailMessage(to="a@x.test", subject="One", text_body="body1")
    second = EmailMessage(to="b@x.test", subject="Two", text_body="body2")

    await sender.send(first)
    await sender.send(second)

    assert sender.outbox == [first, second]


async def test_email_message_is_immutable() -> None:
    """``EmailMessage`` is frozen so a sender can't mutate the caller's payload."""
    from dataclasses import FrozenInstanceError

    msg = EmailMessage(to="a@x.test", subject="hi", text_body="b")
    with pytest.raises(FrozenInstanceError):
        msg.subject = "hacked"  # type: ignore[misc]
