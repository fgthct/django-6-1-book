from datetime import timedelta

import pytest
import redis
from django.conf import settings as django_settings
from django.utils import timezone

from campaigns import limiter
from campaigns.models import Campaign, Contact, Delivery
from campaigns.tasks import send_delivery


@pytest.fixture
def contact(db):
    return Contact.objects.create(email="ana@example.com", name="Ana")


@pytest.fixture
def campaign(db):
    return Campaign.objects.create(
        subject="Autumn news",
        body="Hello {name}, the autumn issue is out.",
        status=Campaign.Status.SENDING,
        started_at=timezone.now(),
    )


@pytest.fixture
def delivery(campaign, contact):
    return Delivery.objects.create(campaign=campaign, contact=contact, due_at=timezone.now())


@pytest.fixture
def no_limit(monkeypatch):
    """The rate limiter always says yes: the send tests don't need Redis."""
    monkeypatch.setattr(limiter, "allow", lambda *a, **k: True)


@pytest.fixture
def fake_queue(settings):
    """A queue that runs nothing and remembers everything: it lets us look at what gets enqueued."""
    settings.TASKS = {"default": {"BACKEND": "django.tasks.backends.dummy.DummyBackend"}}
    from django.tasks import default_task_backend

    default_task_backend.clear()
    yield default_task_backend


@pytest.fixture
def real_redis():
    client = redis.Redis.from_url(django_settings.REDIS_URL)
    try:
        client.ping()
    except redis.ConnectionError:
        pytest.skip("Redis is not reachable")
    return client


def send(delivery) -> str:
    """Run the body of the task right here, without going through any queue."""
    return send_delivery.call(delivery_id=delivery.pk)
