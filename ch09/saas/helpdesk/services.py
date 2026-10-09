"""The business rules: the dashboard and the API both call them."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .models import Comment, Member, Ticket
from .tasks import notify_new_ticket


def require(member, minimum_role):
    if not member.can(minimum_role):
        raise PermissionDenied("insufficient role")


def open_ticket(member, *, title, requester, description="", priority=Ticket.Priority.NORMAL):
    require(member, Member.Role.AGENT)
    ticket = Ticket.objects.create(
        title=title, requester=requester, description=description, priority=priority
    )
    # Never enqueue inside the transaction: on rollback, the notification would talk about a ticket that doesn't exist.
    transaction.on_commit(
        lambda: notify_new_ticket.enqueue(
            organization_id=str(ticket.organization_id), ticket_id=str(ticket.pk)
        )
    )
    return ticket


def assign(member, ticket, assignee):
    """Assigning is for administrators. The assignee must be in the *same* organization:
    the foreign key alone doesn't guarantee it (it knows nothing about tenants)."""
    require(member, Member.Role.ADMIN)
    if assignee is not None and assignee.organization_id != ticket.organization_id:
        raise ValidationError("the assignee does not belong to this organization")
    ticket.assigned = assignee
    ticket.save(update_fields=["assigned"])
    return ticket


def change_status(member, ticket, status):
    require(member, Member.Role.AGENT)
    if status not in Ticket.Status.values:
        raise ValidationError(f"unknown status: {status}")
    ticket.status = status
    ticket.save(update_fields=["status"])
    return ticket


def add_comment(member, ticket, body):
    require(member, Member.Role.AGENT)
    return Comment.objects.create(ticket=ticket, author=member, body=body)
