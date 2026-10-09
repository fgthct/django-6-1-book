import smtplib
from datetime import timedelta

import pytest
from django.utils import timezone

from campaigns import limiter
from campaigns.models import Campaign, Delivery
from campaigns.tasks import backoff_for_attempt

from .conftest import send


def test_a_send_goes_out_through_the_campaigns_mailer(delivery, mailoutbox, no_limit):
    assert send(delivery) == "sent"
    (message,) = mailoutbox
    assert message.sent_using == "campaigns"
    assert message.to == ["ana@example.com"]
    assert message.subject == "Autumn news"


def test_the_text_is_personalized_with_the_name(delivery, mailoutbox, no_limit):
    send(delivery)
    assert mailoutbox[0].body == "Hello Ana, the autumn issue is out."


def test_the_text_is_not_a_template_for_format(campaign, contact, mailoutbox, no_limit):
    campaign.body = "Hi {name.__class__}, {0}, {name}"
    campaign.save()
    delivery = Delivery.objects.create(campaign=campaign, contact=contact)
    send(delivery)
    assert mailoutbox[0].body == "Hi {name.__class__}, {0}, Ana"


def test_a_successful_send_closes_the_delivery(delivery, no_limit, mailoutbox):
    send(delivery)
    delivery.refresh_from_db()
    assert delivery.status == Delivery.Status.SENT
    assert delivery.attempts == 1
    assert delivery.sent_at is not None
    assert delivery.last_error == ""


def test_the_task_is_idempotent(delivery, no_limit, mailoutbox):
    assert send(delivery) == "sent"
    assert send(delivery) == "already handled"
    assert len(mailoutbox) == 1


def test_a_failed_delivery_is_not_sent_again(delivery, no_limit, mailoutbox):
    Delivery.objects.filter(pk=delivery.pk).update(status=Delivery.Status.FAILED)
    assert send(delivery) == "already handled"
    assert mailoutbox == []


def test_an_smtp_error_schedules_a_new_attempt(delivery, mailoutbox, no_limit, fake_queue, monkeypatch, django_capture_on_commit_callbacks):
    def broken(self, *a, **k):
        raise smtplib.SMTPServerDisconnected("connection closed")

    monkeypatch.setattr("django.core.mail.message.EmailMessage.send", broken)
    before = timezone.now()
    with django_capture_on_commit_callbacks(execute=True):
        assert send(delivery) == "to retry"
    delivery.refresh_from_db()
    assert delivery.status == Delivery.Status.PENDING
    assert delivery.attempts == 1
    assert "SMTPServerDisconnected" in delivery.last_error
    (new,) = fake_queue.results
    assert new.kwargs == {"delivery_id": delivery.pk}
    assert before + timedelta(seconds=9) < new.task.run_after < before + timedelta(seconds=12)


def test_the_new_attempt_does_not_start_before_the_commit(delivery, no_limit, fake_queue, monkeypatch):
    monkeypatch.setattr(
        "django.core.mail.message.EmailMessage.send",
        lambda self, *a, **k: (_ for _ in ()).throw(smtplib.SMTPException("no")),
    )
    send(delivery)  # no capture of the callbacks: the commit never happened
    assert fake_queue.results == []


def test_an_os_error_counts_as_a_failed_attempt_too(delivery, no_limit, fake_queue, monkeypatch):
    monkeypatch.setattr(
        "django.core.mail.message.EmailMessage.send",
        lambda self, *a, **k: (_ for _ in ()).throw(ConnectionRefusedError("refused")),
    )
    assert send(delivery) == "to retry"
    delivery.refresh_from_db()
    assert delivery.last_error.startswith("ConnectionRefusedError")


def test_after_the_last_attempt_the_delivery_fails(delivery, no_limit, fake_queue, monkeypatch, settings):
    monkeypatch.setattr(
        "django.core.mail.message.EmailMessage.send",
        lambda self, *a, **k: (_ for _ in ()).throw(smtplib.SMTPException("no")),
    )
    Delivery.objects.filter(pk=delivery.pk).update(attempts=settings.CAMPAIGN_MAX_ATTEMPTS - 1)
    assert send(delivery) == "failed"
    delivery.refresh_from_db()
    assert delivery.status == Delivery.Status.FAILED
    assert delivery.attempts == settings.CAMPAIGN_MAX_ATTEMPTS
    assert fake_queue.results == []


def test_the_attempts_are_counted_in_our_model(delivery, no_limit, fake_queue, monkeypatch):
    monkeypatch.setattr(
        "django.core.mail.message.EmailMessage.send",
        lambda self, *a, **k: (_ for _ in ()).throw(smtplib.SMTPException("no")),
    )
    send(delivery)
    send(delivery)
    delivery.refresh_from_db()
    assert delivery.attempts == 2
    assert delivery.status == Delivery.Status.PENDING


@pytest.mark.parametrize("attempt, seconds", [(1, 10), (2, 20), (3, 40), (4, 80)])
def test_the_backoff_is_exponential(attempt, seconds):
    assert backoff_for_attempt(attempt) == timedelta(seconds=seconds)


def test_over_the_limit_the_send_is_postponed_without_using_an_attempt(delivery, fake_queue, monkeypatch, mailoutbox):
    monkeypatch.setattr(limiter, "allow", lambda *a, **k: False)
    assert send(delivery) == "postponed"
    delivery.refresh_from_db()
    assert delivery.attempts == 0
    assert delivery.status == Delivery.Status.PENDING
    assert mailoutbox == []


def test_the_last_delivery_closes_the_campaign(delivery, campaign, no_limit, mailoutbox):
    send(delivery)
    campaign.refresh_from_db()
    assert campaign.status == Campaign.Status.COMPLETED


def test_the_campaign_stays_open_while_a_delivery_is_pending(delivery, campaign, no_limit, mailoutbox):
    from campaigns.models import Contact

    other = Contact.objects.create(email="bruno@example.com", name="Bruno")
    Delivery.objects.create(campaign=campaign, contact=other)
    send(delivery)
    campaign.refresh_from_db()
    assert campaign.status == Campaign.Status.SENDING
