from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from campaigns.models import Campaign, Contact, Delivery
from campaigns.tasks import requeue_lost


def old(minutes=10):
    return timezone.now() - timedelta(minutes=minutes)


def test_it_requeues_the_pending_deliveries_that_are_long_overdue(delivery, fake_queue):
    Delivery.objects.filter(pk=delivery.pk).update(due_at=old())
    assert requeue_lost() == 1
    (queued,) = fake_queue.results
    assert queued.kwargs == {"delivery_id": delivery.pk}


def test_it_ignores_the_recent_ones(delivery, fake_queue):
    Delivery.objects.filter(pk=delivery.pk).update(due_at=old(minutes=1))
    assert requeue_lost() == 0
    assert fake_queue.results == []


def test_it_does_not_requeue_the_closed_ones(delivery, fake_queue):
    Delivery.objects.filter(pk=delivery.pk).update(due_at=old(), status=Delivery.Status.SENT)
    assert requeue_lost() == 0


def test_it_ignores_deliveries_of_a_campaign_that_is_not_sending(delivery, fake_queue):
    Delivery.objects.filter(pk=delivery.pk).update(due_at=old())
    Campaign.objects.filter(pk=delivery.campaign_id).update(status=Campaign.Status.COMPLETED)
    assert requeue_lost() == 0


def test_after_requeueing_the_deadline_moves_on(delivery, fake_queue):
    Delivery.objects.filter(pk=delivery.pk).update(due_at=old())
    requeue_lost()
    assert requeue_lost() == 0  # the second call finds nothing overdue any more
    delivery.refresh_from_db()
    assert delivery.due_at > old(minutes=1)


def test_a_threshold_of_zero_picks_up_everything_pending(delivery, fake_queue):
    assert requeue_lost(timedelta(0)) == 1


def test_it_redoes_the_preparation_of_a_campaign_without_deliveries(campaign, fake_queue):
    Campaign.objects.filter(pk=campaign.pk).update(started_at=old())
    assert requeue_lost() == 1
    (queued,) = fake_queue.results
    assert queued.kwargs == {"campaign_id": campaign.pk}


def test_a_recent_campaign_without_deliveries_is_left_alone(campaign, fake_queue):
    assert requeue_lost() == 0


def test_the_command_reports_how_many(delivery, fake_queue):
    Delivery.objects.filter(pk=delivery.pk).update(due_at=old())
    out = StringIO()
    call_command("recover_deliveries", stdout=out)
    assert "1 deliveries put back in the queue" in out.getvalue()
