import json
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import services
from .models import CspViolation, Ticket


def reserved(view):
    """It needs an authenticated user *and* a tenant: on the main domain there is nothing to see."""

    @login_required
    @wraps(view)
    def inner(request, *args, **kwargs):
        if request.member is None:
            raise Http404
        return view(request, *args, **kwargs)

    return inner


def home(request):
    if request.member is not None:
        return redirect("dashboard")
    return render(request, "helpdesk/home.html")


def _counters():
    return Ticket.objects.aggregate(
        open=Count("pk", filter=Q(status=Ticket.Status.OPEN)),
        in_progress=Count("pk", filter=Q(status=Ticket.Status.IN_PROGRESS)),
        closed=Count("pk", filter=Q(status=Ticket.Status.CLOSED)),
    )


def _list(request):
    status = request.GET.get("status") or None
    qs = Ticket.objects.select_related("assigned__user")
    if status in Ticket.Status.values:
        qs = qs.filter(status=status)
    else:
        status = None
    page = Paginator(qs, 10).get_page(request.GET.get("page"))
    return {"page": page, "status": status}


@reserved
def dashboard(request):
    context = {"counters": _counters(), **_list(request)}
    template = "helpdesk/dashboard.html"
    if request.headers.get("HX-Request") and request.headers.get("HX-Target") == "ticket-list":
        template += "#ticket_list"
    return render(request, template, context)


@reserved
def counters(request):
    return render(request, "helpdesk/dashboard.html#counters", {"counters": _counters()})


def _comments(ticket):
    return ticket.comments.select_related("author__user")


@reserved
def ticket_detail(request, pk):
    ticket = get_object_or_404(Ticket.objects.select_related("assigned__user"), pk=pk)
    context = {"ticket": ticket, "statuses": Ticket.Status.choices, "comments": _comments(ticket)}
    return render(request, "helpdesk/ticket.html", context)


@reserved
@require_POST
def change_status(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    try:
        services.change_status(request.member, ticket, request.POST.get("status", ""))
    except ValidationError:
        return HttpResponse(status=400)
    return render(request, "helpdesk/ticket.html#status", {"ticket": ticket, "statuses": Ticket.Status.choices})


@reserved
@require_POST
def add_comment(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    body = request.POST.get("body", "").strip()
    if body:
        services.add_comment(request.member, ticket, body)
    return render(request, "helpdesk/ticket.html#comments", {"ticket": ticket, "comments": _comments(ticket)})


BODY_LIMIT = 16_000


def _truncate(value, length):
    return (value or "")[:length]


@csrf_exempt  # it is sent by the browser, not by one of our forms: it can't have the token
@require_POST
def csp_report(request):
    if len(request.body) > BODY_LIMIT:
        return HttpResponse(status=413)
    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponse(status=400)
    # The historical format is {"csp-report": {...}}; the new one (Reporting API) is a list of reports.
    reports = data if isinstance(data, list) else [data]
    saved = []
    for entry in reports:
        if not isinstance(entry, dict):
            continue
        body = entry.get("csp-report") or entry.get("body") or {}
        if not isinstance(body, dict):
            continue
        saved.append(
            CspViolation(
                host=_truncate(request.get_host(), 255),
                directive=_truncate(body.get("effective-directive") or body.get("effectiveDirective")
                                    or body.get("violated-directive"), 100),
                blocked_resource=_truncate(body.get("blocked-uri") or body.get("blockedURL"), 500),
                document=_truncate(body.get("document-uri") or body.get("documentURL"), 500),
                report_only=body.get("disposition") == "report",
            )
        )
    CspViolation.objects.bulk_create(saved[:20])
    return HttpResponse(status=204)
