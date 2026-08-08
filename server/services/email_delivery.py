"""Provider-neutral transactional email delivery."""

from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol


class EmailDeliveryError(RuntimeError):
    """Raised when an email cannot be sent through the configured provider."""


class LoggerLike(Protocol):
    def info(self, msg: str, *args: object) -> None: ...


@dataclass(frozen=True)
class EmailConfig:
    provider: str
    from_address: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_use_tls: bool

    @classmethod
    def from_env(cls) -> "EmailConfig":
        try:
            smtp_port = int(os.getenv("SMTP_PORT") or "587")
        except ValueError as exc:
            raise EmailDeliveryError("SMTP_PORT must be an integer") from exc
        return cls(
            provider=(os.getenv("EMAIL_PROVIDER") or "console").strip().lower(),
            from_address=(
                os.getenv("EMAIL_FROM_ADDRESS") or "OpenMynd <no-reply@openmynd.local>"
            ).strip(),
            smtp_host=(os.getenv("SMTP_HOST") or "").strip(),
            smtp_port=smtp_port,
            smtp_username=(os.getenv("SMTP_USERNAME") or "").strip(),
            smtp_password=(os.getenv("SMTP_PASSWORD") or "").strip(),
            smtp_use_tls=(os.getenv("SMTP_USE_TLS") or "true").strip().lower()
            in {"1", "true", "yes", "on"},
        )


def send_transactional_email(
    *,
    to_address: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    logger: LoggerLike | None = None,
    config: EmailConfig | None = None,
) -> None:
    """Send an email using the configured provider.

    Supported providers:
    - `console`: local/dev mode; logs the email body.
    - `smtp`: uses standard SMTP credentials.
    """
    email_config = config or EmailConfig.from_env()
    provider = email_config.provider
    if provider == "console":
        if logger:
            logger.info(
                "Console email to=%s subject=%s body=%s",
                _redact_email(to_address),
                subject,
                text_body,
            )
        return
    if provider == "smtp":
        _send_smtp_email(
            email_config,
            to_address=to_address,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )
        return
    raise EmailDeliveryError(f"Unsupported EMAIL_PROVIDER '{provider}'")


def _send_smtp_email(
    config: EmailConfig,
    *,
    to_address: str,
    subject: str,
    text_body: str,
    html_body: str | None,
) -> None:
    if not config.smtp_host:
        raise EmailDeliveryError("SMTP_HOST is required when EMAIL_PROVIDER=smtp")

    message = EmailMessage()
    message["From"] = config.from_address
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15) as smtp:
            if config.smtp_use_tls:
                smtp.starttls()
            if config.smtp_username:
                smtp.login(config.smtp_username, config.smtp_password)
            smtp.send_message(message)
    except OSError as exc:
        raise EmailDeliveryError("SMTP email delivery failed") from exc


def _redact_email(email: str) -> str:
    local, separator, domain = str(email or "").partition("@")
    if not separator:
        return "[invalid-email]"
    return f"{local[:2]}***@{domain}"
