import datetime as dt

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from helpdesk import keys, tenant
from helpdesk.api import SafePagination
from helpdesk.models import ApiKey, Ticket

from .conftest import client_api


def test_without_a_key_it_is_401(acme, admin_acme):
    api = client_api(acme, admin_acme)
    assert api.get("/tickets", key="").status_code == 401


def test_an_invented_key_is_401(acme, admin_acme):
    api = client_api(acme, admin_acme)
    assert api.get("/tickets", key="ak_deadbeef_whatever").status_code == 401


def test_a_key_with_an_altered_secret_is_401(acme, admin_acme):
    api = client_api(acme, admin_acme)
    assert api.get("/tickets", key=api.key[:-3] + "xyz").status_code == 401


def test_a_revoked_key_is_401(acme, admin_acme):
    api = client_api(acme, admin_acme)
    assert api.get("/tickets").status_code == 200
    keys.revoke(api.key)
    assert api.get("/tickets").status_code == 401


def test_a_key_of_another_tenant_does_not_work_on_this_subdomain(acme, rossi, admin_acme, admin_rossi):
    rossi_api = client_api(rossi, admin_rossi)
    on_acme = client_api(acme, admin_acme)
    assert on_acme.get("/tickets", key=rossi_api.key).status_code == 401


def test_the_key_is_not_stored_in_clear(acme, admin_acme):
    text = keys.create_key(admin_acme)
    secret = text.split("_", 2)[2]
    stored = ApiKey.objects.latest("pk")
    assert secret not in stored.fingerprint
    assert text not in stored.fingerprint
    assert len(stored.fingerprint) == 64


def test_the_list_only_has_this_tenants_tickets(acme, rossi, admin_acme, ticket_acme, ticket_rossi):
    api = client_api(acme, admin_acme)
    body = api.get("/tickets").json()
    assert body["count"] == 1
    assert [t["title"] for t in body["items"]] == ["Acme ticket"]


def test_the_list_can_be_filtered_by_status(acme, admin_acme, ticket_acme):
    with tenant.tenant(acme):
        Ticket.objects.create(title="done", requester="a@b.test", status="closed")
    api = client_api(acme, admin_acme)
    assert api.get("/tickets", {"status": "closed"}).json()["count"] == 1
    assert api.get("/tickets", {"status": "open"}).json()["count"] == 1


def test_a_huge_limit_is_refused(acme, admin_acme):
    api = client_api(acme, admin_acme)
    assert api.get("/tickets", {"limit": 1000}).status_code == 422


def test_pagination_is_stable_even_with_identical_timestamps(acme, admin_acme):
    moment = timezone.now() - dt.timedelta(hours=1)
    with tenant.tenant(acme):
        for n in range(45):
            Ticket.objects.create(title=f"t{n}", requester="a@b.test")
        Ticket.objects.update(created=moment)
    api = client_api(acme, admin_acme)
    seen = []
    for offset in range(0, 45, 10):
        seen += [t["id"] for t in api.get("/tickets", {"limit": 10, "offset": offset}).json()["items"]]
    assert len(seen) == 45
    assert len(set(seen)) == 45


def test_the_safe_pagination_refuses_an_unordered_queryset(acme, ticket_acme):
    with tenant.tenant(acme):
        unordered = Ticket.objects.order_by("priority")
        with pytest.raises(ImproperlyConfigured):
            SafePagination().paginate_queryset(unordered, SafePagination.Input(limit=5, offset=0), request=None)


def test_the_safe_pagination_accepts_a_complete_ordering(acme, ticket_acme):
    with tenant.tenant(acme):
        ordered = Ticket.objects.order_by("priority", "pk")
        page = SafePagination().paginate_queryset(ordered, SafePagination.Input(limit=5, offset=0), request=None)
        assert len(page["items"]) == 1


def test_get_one_ticket(acme, admin_acme, ticket_acme):
    api = client_api(acme, admin_acme)
    response = api.get(f"/tickets/{ticket_acme.pk}")
    assert response.status_code == 200
    assert response.json()["title"] == "Acme ticket"


def test_another_tenants_ticket_is_404(acme, admin_acme, ticket_rossi):
    api = client_api(acme, admin_acme)
    assert api.get(f"/tickets/{ticket_rossi.pk}").status_code == 404


def test_an_agent_creates_a_ticket(acme, agent_acme):
    api = client_api(acme, agent_acme)
    response = api.post("/tickets", {"title": "New", "requester": "c@x.test"})
    assert response.status_code == 201
    assert response.json()["status"] == "open"


def test_a_reader_cannot_create_a_ticket(acme, reader_acme):
    api = client_api(acme, reader_acme)
    assert api.post("/tickets", {"title": "New", "requester": "c@x.test"}).status_code == 403


def test_an_agent_cannot_assign(acme, agent_acme, ticket_acme):
    api = client_api(acme, agent_acme)
    response = api.post(f"/tickets/{ticket_acme.pk}/assign", {"member_id": agent_acme.pk})
    assert response.status_code == 403


def test_an_administrator_assigns(acme, admin_acme, agent_acme, ticket_acme):
    api = client_api(acme, admin_acme)
    response = api.post(f"/tickets/{ticket_acme.pk}/assign", {"member_id": agent_acme.pk})
    assert response.status_code == 200
    assert response.json()["assigned"]["email"] == "agent@acme.test"


def test_you_cannot_assign_a_member_of_another_tenant(acme, admin_acme, admin_rossi, ticket_acme):
    api = client_api(acme, admin_acme)
    response = api.post(f"/tickets/{ticket_acme.pk}/assign", {"member_id": admin_rossi.pk})
    assert response.status_code == 404


def test_the_list_query_count_is_constant(acme, admin_acme, agent_acme, django_assert_max_num_queries):
    with tenant.tenant(acme):
        for n in range(15):
            Ticket.objects.create(title=f"t{n}", requester="a@b.test", assigned=agent_acme)
    client = client_api(acme, admin_acme)
    with django_assert_max_num_queries(6):
        response = client.get("/tickets", {"limit": 15})
    assert response.status_code == 200 and len(response.json()["items"]) == 15


def test_the_schema_is_public_but_the_interactive_docs_are_not(acme, admin_acme):
    api = client_api(acme, admin_acme)
    assert api.client.get("/api/v1/openapi.json").status_code == 200
    assert api.client.get("/api/v1/docs").status_code == 404


def test_on_the_main_domain_the_key_alone_chooses_the_tenant(acme, rossi, admin_acme, ticket_acme, ticket_rossi):
    """No subdomain, so the middleware chose nothing: the tenant has to come from the key."""
    api = client_api(acme, admin_acme, host="localhost")
    body = api.get("/tickets").json()
    assert [t["title"] for t in body["items"]] == ["Acme ticket"]


def test_the_list_endpoint_refuses_an_incomplete_ordering(acme, admin_acme, ticket_acme, monkeypatch):
    monkeypatch.setattr(Ticket._meta, "ordering", ["-created"])
    api = client_api(acme, admin_acme)
    with pytest.raises(ImproperlyConfigured):
        api.get("/tickets")
