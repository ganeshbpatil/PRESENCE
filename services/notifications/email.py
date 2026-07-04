"""
services/notifications/email.py

SMTP sender for the "email" notification channel — 06_MODULES/
NOTIFICATIONS.md: in-app + email only for v1, no SMS/push. If SMTP_HOST
isn't configured (blank in this environment's .env), logs instead of
raising — the one place a soft-fallback is appropriate, since notification
delivery is non-critical, unlike the billing/attribution paths.

Synchronous (smtplib has no async API) — callers from async code must run
this via asyncio.to_thread, not call it directly (see notifier.py).
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def send_email(
    *,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    from_email: str,
    to_email: str,
    subject: str,
    body: str,
) -> None:
    if not smtp_host:
        logger.info(
            "SMTP not configured -- logging notification instead of sending: to=%s subject=%s",
            to_email,
            subject,
        )
        return

    message = EmailMessage()
    message["From"] = from_email
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
        smtp.starttls()
        if smtp_user:
            smtp.login(smtp_user, smtp_password)
        smtp.send_message(message)
