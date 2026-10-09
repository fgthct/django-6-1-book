import pytest
from django.test import Client

from helpdesk import tenant
from helpdesk.models import Comment, Ticket

from .conftest import client_web


def make_tickets(org, n, **kwargs):
    with tenant.tenant(org):
        for i in range(n):
            Ticket.objects.create(title=f"{org.name} #{i}", requester="a@b.test", **kwargs)


def test_an_anonymous_user_is_sent_to_the_login(acme):
    response = Client(HTTP_HOST="acme.localhost").get("/dashboard/")
    assert response.status_code == 302
    assert response.url == "/login/?next=/dashboard/"


def test_the_main_domain_has_no_dashboard(admin_acme):
    client = Client(HTTP_HOST="localhost")
    client.force_login(admin_acme.user)
    assert client.get("/dashboard/").status_code == 404


def test_an_unknown_subdomain_is_404(db):
    assert Client(HTTP_HOST="nobody.localhost").get("/login/").status_code == 404


def test_someone_who_is_not_a_member_gets_403(rossi, admin_acme):
    client = Client(HTTP_HOST="rossi.localhost")
    client.force_login(admin_acme.user)
    assert client.get("/dashboard/").status_code == 403


def test_the_dashboard_only_shows_this_tenants_tickets(acme, rossi, admin_acme):
    make_tickets(acme, 3)
    make_tickets(rossi, 4)
    response = client_web(acme, admin_acme).get("/dashboard/")
    assert response.status_code == 200
    assert "Acme Inc #0" in response.text
    assert "Rossi" not in response.text


def test_the_counters(acme, admin_acme):
    make_tickets(acme, 2)
    make_tickets(acme, 3, status="closed")
    response = client_web(acme, admin_acme).get("/counters/")
    assert response.context["counters"] == {"open": 2, "in_progress": 0, "closed": 3}


def test_the_htmx_request_returns_only_the_fragment(acme, admin_acme):
    make_tickets(acme, 2)
    web = client_web(acme, admin_acme)
    full = web.get("/dashboard/").text
    fragment = web.get("/dashboard/", headers={"HX-Request": "true", "HX-Target": "ticket-list"}).text
    assert "<html" in full
    assert "<html" not in fragment
    assert "Acme Inc #0" in fragment


def test_the_status_filter(acme, admin_acme):
    make_tickets(acme, 2)
    make_tickets(acme, 3, status="closed")
    page = client_web(acme, admin_acme).get("/dashboard/", {"status": "closed"}).context["page"]
    assert page.paginator.count == 3


def test_an_invalid_status_is_ignored(acme, admin_acme):
    make_tickets(acme, 2)
    response = client_web(acme, admin_acme).get("/dashboard/", {"status": "banana"})
    assert response.status_code == 200
    assert response.context["page"].paginator.count == 2


def test_pagination(acme, admin_acme):
    make_tickets(acme, 25)
    page = client_web(acme, admin_acme).get("/dashboard/", {"page": 3}).context["page"]
    assert len(page) == 5


def test_the_dashboard_has_a_constant_number_of_queries(acme, admin_acme, agent_acme, django_assert_max_num_queries):
    make_tickets(acme, 10)
    with tenant.tenant(acme):
        Ticket.objects.update(assigned=agent_acme)
    web = client_web(acme, admin_acme)
    with django_assert_max_num_queries(8):
        assert web.get("/dashboard/").status_code == 200


def test_another_tenants_ticket_is_404(acme, admin_acme, ticket_rossi):
    assert client_web(acme, admin_acme).get(f"/tickets/{ticket_rossi.pk}/").status_code == 404


def test_an_agent_changes_the_status(acme, agent_acme, ticket_acme):
    response = client_web(acme, agent_acme).post(f"/tickets/{ticket_acme.pk}/status/", {"status": "closed"})
    assert response.status_code == 200
    with tenant.tenant(acme):
        assert Ticket.objects.get(pk=ticket_acme.pk).status == "closed"


def test_a_reader_cannot_change_the_status(acme, reader_acme, ticket_acme):
    response = client_web(acme, reader_acme).post(f"/tickets/{ticket_acme.pk}/status/", {"status": "closed"})
    assert response.status_code == 403


def test_the_status_of_another_tenants_ticket_is_404(acme, admin_acme, ticket_rossi):
    response = client_web(acme, admin_acme).post(f"/tickets/{ticket_rossi.pk}/status/", {"status": "closed"})
    assert response.status_code == 404


def test_an_invalid_status_is_a_400(acme, agent_acme, ticket_acme):
    response = client_web(acme, agent_acme).post(f"/tickets/{ticket_acme.pk}/status/", {"status": "banana"})
    assert response.status_code == 400


def test_a_comment_is_added(acme, agent_acme, ticket_acme):
    response = client_web(acme, agent_acme).post(f"/tickets/{ticket_acme.pk}/comments/", {"body": "On it"})
    assert response.status_code == 200
    with tenant.tenant(acme):
        assert Comment.objects.get().body == "On it"


def test_the_root_leads_to_the_dashboard(acme, admin_acme):
    response = client_web(acme, admin_acme).get("/")
    assert response.status_code == 302
    assert response.url == "/dashboard/"


def test_no_tenant_stays_active_after_a_request(acme, admin_acme):
    client_web(acme, admin_acme).get("/dashboard/")
    assert tenant.current_or_none() is None
