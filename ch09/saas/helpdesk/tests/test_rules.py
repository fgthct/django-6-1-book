import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from helpdesk import services, tenant
from helpdesk.models import Member, Ticket


def test_a_reader_cannot_open_tickets(acme, reader_acme):
    with tenant.tenant(acme):
        with pytest.raises(PermissionDenied):
            services.open_ticket(reader_acme, title="x", requester="a@b.test")


def test_an_agent_can_open_tickets(acme, agent_acme):
    with tenant.tenant(acme):
        ticket = services.open_ticket(agent_acme, title="x", requester="a@b.test")
    assert ticket.status == Ticket.Status.OPEN


def test_an_agent_cannot_assign(acme, agent_acme, ticket_acme):
    with tenant.tenant(acme):
        with pytest.raises(PermissionDenied):
            services.assign(agent_acme, ticket_acme, agent_acme)


def test_an_administrator_assigns(acme, admin_acme, agent_acme, ticket_acme):
    with tenant.tenant(acme):
        services.assign(admin_acme, ticket_acme, agent_acme)
        assert Ticket.objects.get(pk=ticket_acme.pk).assigned_id == agent_acme.pk


def test_the_assignee_must_belong_to_the_same_organization(acme, admin_acme, admin_rossi, ticket_acme):
    with tenant.tenant(acme):
        with pytest.raises(ValidationError):
            services.assign(admin_acme, ticket_acme, admin_rossi)


def test_an_unknown_status_is_rejected(acme, agent_acme, ticket_acme):
    with tenant.tenant(acme):
        with pytest.raises(ValidationError):
            services.change_status(agent_acme, ticket_acme, "banana")


def test_a_reader_cannot_change_the_status(acme, reader_acme, ticket_acme):
    with tenant.tenant(acme):
        with pytest.raises(PermissionDenied):
            services.change_status(reader_acme, ticket_acme, "closed")


def test_a_reader_cannot_comment(acme, reader_acme, ticket_acme):
    with tenant.tenant(acme):
        with pytest.raises(PermissionDenied):
            services.add_comment(reader_acme, ticket_acme, "hi")


def test_one_role_per_organization(acme, admin_acme):
    with pytest.raises(IntegrityError), transaction.atomic():
        Member.objects.create(user=admin_acme.user, organization=acme, role=Member.Role.READER)


def test_the_same_user_can_belong_to_two_organizations(acme, rossi, admin_acme):
    Member.objects.create(user=admin_acme.user, organization=rossi, role=Member.Role.READER)
    assert admin_acme.user.memberships.count() == 2
