"""SMTP notifier with retries and backoff."""
from __future__ import annotations

import asyncio
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.config import get_settings
from app.notifier.base import Notifier

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_BASE = 2


class SMTPNotifier(Notifier):
    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        use_tls: bool = True,
    ):
        s = get_settings()
        self.host = host or s.smtp_host
        self.port = port or s.smtp_port
        self.user = user or s.smtp_user
        self.password = password or s.smtp_pass
        self.use_tls = use_tls if (user or password) else s.smtp_use_tls

    async def send(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> None:
        from_addr = get_settings().support_email or self.user or "noreply@localhost"
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to
        msg.attach(MIMEText(body_text, "plain"))
        if body_html:
            msg.attach(MIMEText(body_html, "html"))

        last_err = None
        for attempt in range(MAX_RETRIES):
            try:
                await aiosmtplib.send(
                    msg,
                    hostname=self.host,
                    port=self.port,
                    username=self.user or None,
                    password=self.password or None,
                    use_tls=self.use_tls,
                    sender=from_addr,
                )
                return
            except Exception as e:
                last_err = e
                logger.warning("SMTP send attempt %s failed: %s", attempt + 1, e)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(BACKOFF_BASE ** attempt)
        raise last_err  # type: ignore


def get_notifier() -> Notifier:
    return SMTPNotifier()
