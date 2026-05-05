"""Pluggable email sender.

The auth flow needs to send four kinds of message: account verification,
password reset, MFA setup confirmation, and (in the future) invitations.
Rather than couple the service layer to a specific provider, we depend on
:class:`EmailSender`.

In v0 we only implement two senders:

* :class:`ConsoleEmailSender` — dev default. Writes the message to stdout
  with a clear divider so you can copy the verification link from the
  terminal.
* :class:`CapturingEmailSender` — for tests. Stores every call in
  :attr:`outbox` so assertions can inspect them.

A real SMTP / SendGrid / Resend sender slots in by implementing
:meth:`EmailSender.send`.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EmailMessage:
    to: str
    subject: str
    text_body: str
    html_body: str | None = None


class EmailSender(ABC):
    """Async-only by design: every concrete sender will eventually do I/O."""

    @abstractmethod
    async def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailSender(EmailSender):
    """Print every email to stdout, framed for visibility in `fastapi dev` logs.

    The frame is intentionally noisy: in dev you want the verification
    link to be impossible to miss in the terminal scroll.
    """

    async def send(self, message: EmailMessage) -> None:
        divider = "=" * 60
        rendered = (
            f"\n{divider}\n"
            f"[email] To:      {message.to}\n"
            f"[email] Subject: {message.subject}\n"
            f"{'-' * 60}\n"
            f"{message.text_body}\n"
            f"{divider}\n"
        )
        # We deliberately use print rather than the logger: the SensitiveData
        # filter would redact any "token=..." patterns inside the body, and
        # the whole point of the dev sender is that you can copy them.
        print(rendered)


@dataclass(slots=True)
class CapturingEmailSender(EmailSender):
    """Test sender. Holds every message in :attr:`outbox` (newest last)."""

    outbox: list[EmailMessage] = field(default_factory=list)

    async def send(self, message: EmailMessage) -> None:
        self.outbox.append(message)
