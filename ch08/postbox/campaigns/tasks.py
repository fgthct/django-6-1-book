import smtplib
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.tasks import task
from django.utils import timezone

from . import limiter
from .models import Campaign, Contact, Delivery


def backoff_for_attempt(attempt: int) -> timedelta:
    """Exponential backoff: 10 s, 20 s, 40 s… (the base lives in the settings)."""
    return timedelta(seconds=settings.CAMPAIGN_BASE_WAIT * 2 ** (attempt - 1))


def _retry(delivery_id: int, wait: timedelta) -> None:
    # The new task starts only after the commit: otherwise a fast worker
    # could read the row before this transaction has updated it.
    when = timezone.now() + wait
    Delivery.objects.filter(pk=delivery_id).update(due_at=when)
    transaction.on_commit(lambda: send_delivery.using(run_after=when).enqueue(delivery_id=delivery_id))


def _close_if_finished(campaign_id: int) -> None:
    still_pending = Exists(
        Delivery.objects.filter(campaign=OuterRef("pk"), status=Delivery.Status.PENDING)
    )
    Campaign.objects.filter(pk=campaign_id, status=Campaign.Status.SENDING).exclude(
        still_pending
    ).update(status=Campaign.Status.COMPLETED)


@task
def send_delivery(delivery_id: int) -> str:
    """Send one message. Returns what happened, as text."""
    with transaction.atomic():
        delivery = (
            Delivery.objects.select_for_update()
            .select_related("campaign", "contact")
            .get(pk=delivery_id)
        )
        # 1. Another copy of the task may already have closed it.
        if delivery.status != Delivery.Status.PENDING:
            return "already handled"

        # 2. A rate limit shared by all the workers.
        if not limiter.allow("campaigns", settings.CAMPAIGN_SENDS_PER_SECOND):
            _retry(delivery_id, timedelta(seconds=1))
            return "postponed"

        # 3. The actual send.
        body = delivery.campaign.body.replace("{name}", delivery.contact.name)
        message = EmailMessage(
            subject=delivery.campaign.subject,
            body=body,
            from_email=settings.CAMPAIGN_SENDER,
            to=[delivery.contact.email],
        )
        delivery.attempts += 1
        try:
            message.send(using="campaigns")
        except (smtplib.SMTPException, OSError) as error:
            delivery.last_error = f"{type(error).__name__}: {error}"
            if delivery.attempts >= settings.CAMPAIGN_MAX_ATTEMPTS:
                delivery.status = Delivery.Status.FAILED
                outcome = "failed"
            else:
                _retry(delivery_id, backoff_for_attempt(delivery.attempts))
                outcome = "to retry"
        else:
            delivery.status = Delivery.Status.SENT
            delivery.sent_at = timezone.now()
            delivery.last_error = ""
            outcome = "sent"
        delivery.save()
    _close_if_finished(delivery.campaign_id)
    return outcome


@task
def prepare_deliveries(campaign_id: int) -> int:
    """Create a Delivery for every active contact and enqueue one send for each.

    It may run twice (a queue delivers *at least once*, not *exactly
    once*): that is why `ignore_conflicts` and the send that checks the status.
    """
    campaign = Campaign.objects.get(pk=campaign_id)
    if campaign.status != Campaign.Status.SENDING:
        return 0
    Delivery.objects.bulk_create(
        [
            Delivery(campaign=campaign, contact=c, due_at=timezone.now())
            for c in Contact.objects.filter(active=True)
        ],
        ignore_conflicts=True,
    )
    pending = campaign.deliveries.filter(status=Delivery.Status.PENDING)
    to_send = list(pending.values_list("pk", flat=True))
    pending.update(due_at=timezone.now())
    for pk in to_send:
        send_delivery.enqueue(delivery_id=pk)
    _close_if_finished(campaign_id)  # no active contacts: finished right away
    return len(to_send)


def requeue_lost(older_than: timedelta = timedelta(minutes=5)) -> int:
    """Put back in the queue what should have started long ago and hasn't.

    A worker killed mid-job tells nobody: its task stays "running"
    forever and the delivery stays "pending". Run this function
    now and then (cron, a systemd timer). It is safe: a send that
    finds the delivery already closed does nothing, and the
    preparation can run twice without harm.
    """
    limit = timezone.now() - older_than

    # 1. Campaigns started a while ago that don't have a single delivery:
    #    the preparation task was lost before it began.
    without_deliveries = Campaign.objects.filter(
        status=Campaign.Status.SENDING, started_at__lt=limit
    ).exclude(Exists(Delivery.objects.filter(campaign=OuterRef("pk"))))
    campaigns = list(without_deliveries.values_list("pk", flat=True))
    Campaign.objects.filter(pk__in=campaigns).update(started_at=timezone.now())
    for pk in campaigns:
        prepare_deliveries.enqueue(campaign_id=pk)

    # 2. Pending deliveries whose time passed a while ago.
    lost = Delivery.objects.filter(
        status=Delivery.Status.PENDING,
        campaign__status=Campaign.Status.SENDING,
        due_at__lt=limit,
    )
    pks = list(lost.values_list("pk", flat=True))
    Delivery.objects.filter(pk__in=pks).update(due_at=timezone.now())
    for pk in pks:
        send_delivery.enqueue(delivery_id=pk)
    return len(campaigns) + len(pks)
