"""Email providers: smtp (real) or mock (logs only)."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from functools import lru_cache
from typing import List, Optional

from app.core.config import settings

log = logging.getLogger("email")


class EmailProvider:
    name = "base"

    def send(self, to: str, subject: str, body: str, html: Optional[str] = None) -> bool:
        raise NotImplementedError


class MockEmail(EmailProvider):
    name = "mock"
    sent: List[dict] = []

    def send(self, to: str, subject: str, body: str, html: Optional[str] = None) -> bool:
        log.info("[mock email] to=%s subject=%s", to, subject)
        MockEmail.sent.append({"to": to, "subject": subject, "body": body})
        return True


class SMTPEmail(EmailProvider):
    name = "smtp"

    def send(self, to: str, subject: str, body: str, html: Optional[str] = None) -> bool:
        msg = EmailMessage()
        msg["From"] = settings.smtp_from or settings.smtp_user
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        if html:
            msg.add_alternative(html, subtype="html")
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=25) as s:
                s.ehlo()
                s.starttls()
                s.ehlo()
                if settings.smtp_user:
                    s.login(settings.smtp_user, settings.smtp_password.replace(" ", ""))
                s.send_message(msg)
            log.info("email sent to %s: %s", to, subject)
            return True
        except smtplib.SMTPAuthenticationError as exc:
            log.error("SMTP login rejected for %s (%s). Create a new Gmail app password and update SMTP_PASSWORD in .env.", settings.smtp_user, exc.smtp_error[:120] if exc.smtp_error else exc)
        except Exception as exc:
            log.error("email to %s failed: %s", to, exc)
        return False


@lru_cache
def get_email() -> EmailProvider:
    if settings.email_provider.lower() == "smtp" and settings.smtp_host:
        return SMTPEmail()
    return MockEmail()
