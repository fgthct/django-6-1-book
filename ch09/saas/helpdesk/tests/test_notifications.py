import pytest
from django.core.exceptions import ValidationError

from helpdesk import services, tenant
from helpdesk.models import Organization, Ticket
from helpdesk.tasks import notify_new_ticket


@pytest.fixture
def fake_queue(settings):
    settings.TASKS = {"default": {"BACKEND": "django.tasks.backends.dummy.DummyBackend"}}
    from django.tasks import default_task_backend

    default_task_backend.clear()
    yield default_task_backend


def test_the_notification_is_enqueued_only_after_the_commit(
    acme, agent_acme, fake_queue, django_capture_on_commit_callbacks
):
    with tenant.tenant(acme):
        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            services.open_ticket(agent_acme, title="x", requester="a@b.test")
        assert fake_queue.results == []
        for callback in callbacks:
            callback()
    assert len(fake_queue.results) == 1


def test_the_enqueued_task_carries_identifiers_not_objects(
    acme, agent_acme, fake_queue, django_capture_on_commit_callbacks
):
    with tenant.tenant(acme):
        with django_capture_on_commit_callbacks(execute=True):
            ticket = services.open_ticket(agent_acme, title="x", requester="a@b.test")
    (result,) = fake_queue.results
    assert result.kwargs == {"organization_id": str(acme.pk), "ticket_id": str(ticket.pk)}


def test_the_task_writes_to_the_administrators_only(acme, ticket_acme, mailoutbox):
    sent = notify_new_ticket.call(organization_id=str(acme.pk), ticket_id=str(ticket_acme.pk))
    assert sent == 1
    (message,) = mailoutbox
    assert message.to == ["admin@acme.test"]
    assert "Acme ticket" in message.subject


def test_each_tenant_uses_its_own_mailer(acme, rossi, ticket_acme, ticket_rossi, mailoutbox):
    Organization.objects.filter(pk=rossi.pk).update(mailer="dedicated")
    notify_new_ticket.call(organization_id=str(acme.pk), ticket_id=str(ticket_acme.pk))
    notify_new_ticket.call(organization_id=str(rossi.pk), ticket_id=str(ticket_rossi.pk))
    assert [m.sent_using for m in mailoutbox] == ["default", "dedicated"]


def test_the_task_reopens_its_own_tenant(acme, ticket_acme, mailoutbox):
    assert tenant.current_or_none() is None
    notify_new_ticket.call(organization_id=str(acme.pk), ticket_id=str(ticket_acme.pk))
    assert tenant.current_or_none() is None


def test_another_tenants_ticket_is_not_found_and_nothing_is_sent(acme, ticket_rossi, mailoutbox):
    with pytest.raises(Ticket.DoesNotExist):
        notify_new_ticket.call(organization_id=str(acme.pk), ticket_id=str(ticket_rossi.pk))
    assert mailoutbox == []


def test_an_unknown_mailer_is_rejected_by_the_model(db):
    with pytest.raises(ValidationError) as error:
        Organization(slug="x", name="X", mailer="nope").full_clean()
    assert "mailer" in error.value.message_dict
