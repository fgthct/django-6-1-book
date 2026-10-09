from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Campaign, Delivery
from .tasks import prepare_deliveries
from django.db import transaction


def index(request):
    return render(request, "campaigns/index.html", {"campaigns": Campaign.objects.all()})


@require_POST
def create(request):
    campaign = Campaign.objects.create(
        subject=request.POST["subject"], body=request.POST["body"]
    )
    return redirect("detail", pk=campaign.pk)


def _counts(campaign: Campaign) -> dict:
    c = campaign.deliveries.aggregate(
        total=Count("pk"),
        sent=Count("pk", filter=Q(status=Delivery.Status.SENT)),
        pending=Count("pk", filter=Q(status=Delivery.Status.PENDING)),
        failed=Count("pk", filter=Q(status=Delivery.Status.FAILED)),
    )
    done = c["sent"] + c["failed"]
    c["percentage"] = round(100 * done / c["total"]) if c["total"] else 0
    return c


def detail(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    return render(request, "campaigns/detail.html", {"campaign": campaign, "counts": _counts(campaign)})


def progress(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    return render(request, "campaigns/detail.html#progress", {"campaign": campaign, "counts": _counts(campaign)})


@require_POST
def start(request, pk):
    # The draft → sending change is a conditional UPDATE: if two people
    # press the button together, only one still finds the draft.
    with transaction.atomic():
        moved = Campaign.objects.filter(pk=pk, status=Campaign.Status.DRAFT).update(
            status=Campaign.Status.SENDING, started_at=timezone.now()
        )
        if moved:
            transaction.on_commit(lambda: prepare_deliveries.enqueue(campaign_id=pk))
    return redirect("detail", pk=pk)
