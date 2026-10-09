import pytest
from django.core.exceptions import FieldFetchBlocked
from django.apps import apps
from django.db import models

from helpdesk import tenant
from helpdesk.models import Comment, Member, Ticket, TenantManager, TenantModel

def test_without_a_tenant_the_manager_fails_closed(db):
    with pytest.raises(tenant.MissingTenant):
        Ticket.objects.all()
    with pytest.raises(tenant.MissingTenant):
        Ticket.objects.count()


def test_a_context_without_a_tenant_is_not_enough(db):
    with tenant.tenant():
        with pytest.raises(tenant.MissingTenant):
            Ticket.objects.all()


def test_you_only_see_the_active_tenants_rows(acme, rossi, ticket_acme, ticket_rossi):
    with tenant.tenant(acme):
        assert list(Ticket.objects.all()) == [ticket_acme]
    with tenant.tenant(rossi):
        assert list(Ticket.objects.all()) == [ticket_rossi]


def test_another_tenants_id_simply_does_not_exist(acme, ticket_rossi):
    with tenant.tenant(acme):
        with pytest.raises(Ticket.DoesNotExist):
            Ticket.objects.get(pk=ticket_rossi.pk)


def test_every_tenant_model_uses_the_tenant_manager():
    """One rule, checked for every model: whoever adds a model and forgets the manager finds out here."""
    global_models = {"Member", "Organization", "ApiKey", "CspViolation"}  # outside the filter, by choice
    for model in apps.get_app_config("helpdesk").get_models():
        if model.__name__ in global_models:
            continue
        assert issubclass(model, TenantModel), model
        assert isinstance(model._default_manager, TenantManager), model


def test_the_global_models_are_really_the_only_ones_left_out():
    outside = {
        m.__name__ for m in apps.get_app_config("helpdesk").get_models() if not issubclass(m, TenantModel)
    }
    assert outside == {"Member", "Organization", "ApiKey", "CspViolation"}


def test_the_reverse_relation_is_filtered_too(acme, rossi, ticket_acme):
    with tenant.tenant(acme):
        Comment.objects.create(ticket=ticket_acme, body="hello")
        assert ticket_acme.comments.count() == 1
    with tenant.tenant(rossi):
        assert Comment.objects.count() == 0


def test_writing_into_another_tenant_is_refused(acme, rossi, ticket_acme):
    with tenant.tenant(rossi):
        with pytest.raises(PermissionError):
            ticket_acme.save()


def test_saving_sets_the_active_tenant(acme):
    with tenant.tenant(acme):
        ticket = Ticket.objects.create(title="t", requester="a@b.test")
    assert ticket.organization_id == acme.pk


def test_contexts_nest_and_restore_the_previous_one(acme, rossi):
    with tenant.tenant(acme):
        with tenant.tenant(rossi):
            assert tenant.current() == rossi
        assert tenant.current() == acme
    assert tenant.current_or_none() is None


def test_the_unfiltered_door_sees_everything(acme, rossi, ticket_acme, ticket_rossi):
    assert Ticket.unfiltered.count() == 2


def test_the_fetch_mode_raise_rule_is_active(acme, agent_acme, ticket_acme):
    """In tests, a lazy load that escapes us is an error."""
    with tenant.tenant(acme):
        Ticket.objects.filter(pk=ticket_acme.pk).update(assigned=agent_acme)
        ticket = Ticket.objects.get(pk=ticket_acme.pk)
        with pytest.raises(FieldFetchBlocked):
            ticket.assigned
