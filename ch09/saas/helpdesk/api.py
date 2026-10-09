from datetime import datetime
from uuid import UUID

from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.http import Http404
from ninja import NinjaAPI, Schema, Status
from ninja.pagination import LimitOffsetPagination, paginate
from ninja.security import HttpBearer

from . import keys, services, tenant
from .models import Member, Ticket


class ApiKeyAuth(HttpBearer):
    def authenticate(self, request, token):
        member = keys.verify(token)
        if member is None:
            return None
        # If the request arrives on a subdomain, the key must belong to *that* tenant.
        if request.organization is not None and request.organization != member.organization:
            return None
        tenant.activate(member.organization)
        request.member = member
        return member


api = NinjaAPI(auth=ApiKeyAuth(), docs_url=None, urls_namespace="api")


@api.exception_handler(PermissionDenied)
def forbidden(request, exc):
    return api.create_response(request, {"detail": str(exc) or "forbidden"}, status=403)


@api.exception_handler(ValidationError)
def invalid(request, exc):
    return api.create_response(request, {"detail": exc.messages}, status=400)


@api.exception_handler(Http404)
def not_found(request, exc):
    return api.create_response(request, {"detail": "not found"}, status=404)


class TicketOut(Schema):
    id: UUID
    title: str
    description: str
    requester: str
    status: str
    priority: int
    assigned: MemberOut | None
    created: datetime


class MemberOut(Schema):
    id: int
    email: str
    role: int

    @staticmethod
    def resolve_email(obj):
        return obj.user.email


class TicketIn(Schema):
    title: str
    requester: str
    description: str = ""
    priority: int = Ticket.Priority.NORMAL


class AssignIn(Schema):
    member_id: int | None = None


class SafePagination(LimitOffsetPagination):
    """Like LimitOffsetPagination, but it refuses to paginate a non-deterministic ordering."""

    def paginate_queryset(self, queryset, pagination, **params):
        if hasattr(queryset, "totally_ordered") and not queryset.totally_ordered:
            raise ImproperlyConfigured(
                "Pagination on a queryset without a complete ordering: pages with "
                "duplicate or missing rows. Add a unique field (e.g. 'pk') to the order_by."
            )
        return super().paginate_queryset(queryset, pagination, **params)


def _ticket_or_404(pk):
    try:
        return Ticket.objects.select_related("assigned__user").get(pk=pk)
    except Ticket.DoesNotExist:
        raise Http404 from None


@api.get("/tickets", response=list[TicketOut])
@paginate(SafePagination)
def list_tickets(request, status: str | None = None):
    qs = Ticket.objects.select_related("assigned__user")
    if status:
        qs = qs.filter(status=status)
    return qs


@api.get("/tickets/{ticket_id}", response=TicketOut)
def get_ticket(request, ticket_id: UUID):
    return _ticket_or_404(ticket_id)


@api.post("/tickets", response={201: TicketOut})
def create_ticket(request, data: TicketIn):
    ticket = services.open_ticket(request.member, **data.dict())
    return Status(201, _ticket_or_404(ticket.pk))


@api.post("/tickets/{ticket_id}/assign", response=TicketOut)
def assign_ticket(request, ticket_id: UUID, data: AssignIn):
    ticket = _ticket_or_404(ticket_id)
    assignee = None
    if data.member_id is not None:
        try:
            assignee = Member.objects.get(pk=data.member_id, organization=request.member.organization)
        except Member.DoesNotExist:
            raise Http404 from None
    services.assign(request.member, ticket, assignee)
    return _ticket_or_404(ticket.pk)
