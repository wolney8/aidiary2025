import pytest

from services.email_delivery import (
    EmailConfig,
    EmailDeliveryError,
    send_transactional_email,
)


class _Logger:
    def __init__(self):
        self.messages: list[tuple[str, tuple[object, ...]]] = []

    def info(self, msg: str, *args: object) -> None:
        self.messages.append((msg, args))


def test_console_email_logs_redacted_recipient():
    logger = _Logger()

    send_transactional_email(
        to_address="will@example.com",
        subject="Subject",
        text_body="Body",
        logger=logger,
        config=EmailConfig(
            provider="console",
            from_address="OpenMynd <no-reply@openmynd.local>",
            smtp_host="",
            smtp_port=587,
            smtp_username="",
            smtp_password="",
            smtp_use_tls=True,
        ),
    )

    assert logger.messages
    assert "wi***@example.com" in str(logger.messages[0])
    assert "will@example.com" not in str(logger.messages[0])


def test_email_delivery_rejects_unknown_provider():
    with pytest.raises(EmailDeliveryError, match="Unsupported EMAIL_PROVIDER"):
        send_transactional_email(
            to_address="user@example.com",
            subject="Subject",
            text_body="Body",
            config=EmailConfig(
                provider="unknown",
                from_address="OpenMynd <no-reply@openmynd.local>",
                smtp_host="",
                smtp_port=587,
                smtp_username="",
                smtp_password="",
                smtp_use_tls=True,
            ),
        )


def test_email_config_rejects_invalid_smtp_port(monkeypatch):
    monkeypatch.setenv("SMTP_PORT", "not-a-number")

    with pytest.raises(EmailDeliveryError, match="SMTP_PORT must be an integer"):
        EmailConfig.from_env()
