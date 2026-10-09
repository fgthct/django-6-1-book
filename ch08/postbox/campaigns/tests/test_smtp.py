import email
import email.policy
import smtplib

import pytest
from aiosmtpd.controller import Controller

from campaigns.models import Delivery

from .conftest import send
from .helpers import Collector, free_port


@pytest.fixture
def smtp_server(settings):
    collector = Collector()
    port = free_port()
    controller = Controller(collector, hostname="127.0.0.1", port=port)
    controller.start()
    # pytest-django replaces every mailer with locmem: here we put SMTP back, for this test only
    settings.MAILERS = {
        "default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"},
        "campaigns": {
            "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "OPTIONS": {"host": "127.0.0.1", "port": port, "timeout": 5},
        },
    }
    yield collector
    controller.stop()


def test_a_real_smtp_dialogue(delivery, no_limit, smtp_server):
    delivery.campaign.subject = "News from the café"
    delivery.campaign.save()
    assert send(delivery) == "sent"
    (envelope,) = smtp_server.messages
    assert envelope.rcpt_tos == ["ana@example.com"]
    assert envelope.mail_from == "news@postbox.example"
    raw = envelope.content
    assert b"=?utf-8?" in raw.split(b"\n\n")[0]  # on the wire the subject travels encoded
    message = email.message_from_bytes(raw, policy=email.policy.default)
    assert message["Subject"] == "News from the café"
    assert "Hello Ana" in message.get_content()


def test_with_the_server_down_the_attempt_is_recorded(delivery, no_limit, fake_queue, settings):
    settings.MAILERS = {
        "default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"},
        "campaigns": {
            "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "OPTIONS": {"host": "127.0.0.1", "port": free_port(), "timeout": 2},
        },
    }
    assert send(delivery) == "to retry"
    delivery.refresh_from_db()
    assert delivery.last_error.startswith("ConnectionRefusedError")
    assert delivery.status == Delivery.Status.PENDING
