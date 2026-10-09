from django.conf import settings
from django.core.mail import EmailMessage
from django.tasks import task

from . import tenant
from .models import Member, Organization, Ticket


@task
def notify_new_ticket(organization_id, ticket_id):
    """Notify the administrators. A task doesn't live inside the request: the tenant
    isn't there, and has to be reopened starting from the identifier we were given."""
    organization = Organization.objects.get(pk=organization_id)
    with tenant.tenant(organization):
        ticket = Ticket.objects.get(pk=ticket_id)
        recipients = list(
            Member.objects.filter(organization=organization, role=Member.Role.ADMIN)
            .select_related("user")
            .values_list("user__email", flat=True)
        )
        if not recipients:
            return 0
        EmailMessage(
            subject=f"[{organization.name}] New ticket: {ticket.title}",
            body=f"{ticket.requester} opened a ticket.\n\n{ticket.description}",
            from_email=settings.HELPDESK_FROM,
            to=recipients,
        ).send(using=organization.mailer)
        return len(recipients)
