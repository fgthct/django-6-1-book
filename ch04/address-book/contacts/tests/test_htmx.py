from django.test import Client
from django.urls import reverse

from contacts.models import Contact

HTMX = {"HTTP_HX_REQUEST": "true"}


def test_normal_request_returns_full_page(client, contacts):
    r = client.get(reverse("contacts:list"))
    assert "<html" in r.text and "<h1>" in r.text


def test_htmx_request_returns_only_the_fragment(client, contacts):
    r = client.get(reverse("contacts:list"), **HTMX)
    assert "<html" not in r.text and "<h1>" not in r.text
    assert "Person 00" in r.text


def test_response_varies_on_hx_request(client, contacts):
    r = client.get(reverse("contacts:list"))
    assert "HX-Request" in r["Vary"]


def test_history_restore_wants_the_full_page(client, contacts):
    r = client.get(reverse("contacts:list"), **HTMX, HTTP_HX_HISTORY_RESTORE_REQUEST="true")
    assert "<html" in r.text


def test_search_filters_by_city(client, contacts):
    r = client.get(reverse("contacts:list"), {"q": "boston"}, **HTMX)
    assert "Person 00" in r.text and "Person 01" not in r.text


def test_pagination_load_more(client, contacts):
    r1 = client.get(reverse("contacts:list"), **HTMX)
    assert "load-more" in r1.text and "Person 10" not in r1.text
    r3 = client.get(reverse("contacts:list"), {"page": 3}, **HTMX)
    assert "Person 24" in r3.text and "load-more" not in r3.text


def test_queryset_has_a_total_ordering(contacts):
    assert Contact.objects.all().totally_ordered


def test_valid_edit_returns_the_row(client, contacts):
    c = contacts[0]
    r = client.post(
        reverse("contacts:edit", args=[c.pk]),
        {"name": "Ada Lovelace", "email": c.email},
        **HTMX,
    )
    assert r.status_code == 200
    assert "Ada Lovelace" in r.text and "<form" not in r.text


def test_invalid_edit_stays_200_with_errors(client, contacts):
    c = contacts[0]
    r = client.post(reverse("contacts:edit", args=[c.pk]),
                    {"name": "X", "email": contacts[1].email}, **HTMX)
    # HTMX 2 never swaps 4xx responses: form errors must travel with 200
    assert r.status_code == 200 and "errorlist" in r.text


def test_htmx_create_responds_with_new_form_row_and_oob_counter(client, contacts):
    r = client.post(reverse("contacts:new"),
                    {"name": "Ada", "email": "ada@example.com"}, **HTMX)
    assert r.status_code == 200
    assert 'id="new-form"' in r.text
    assert 'hx-swap-oob="afterbegin:#rows"' in r.text and "<template>" in r.text
    assert 'hx-swap-oob="true"' in r.text and "(26 contacts)" in r.text


def test_create_without_htmx_redirects(client, db):
    r = client.post(reverse("contacts:new"), {"name": "Ada", "email": "ada@example.com"})
    assert r.status_code == 302 and Contact.objects.count() == 1


def test_invalid_create_without_htmx_shows_full_page(client, db):
    r = client.post(reverse("contacts:new"), {"name": "", "email": "x"})
    assert r.status_code == 200 and "<html" in r.text and "errorlist" in r.text


def test_delete_emits_trigger_and_not_204(client, contacts):
    pk = contacts[0].pk
    r = client.delete(reverse("contacts:delete", args=[pk]), **HTMX)
    assert r.status_code == 200  # 204 does not swap the DOM: the row would stay
    assert r["HX-Trigger"] == "contactsChanged"
    assert not Contact.objects.filter(pk=pk).exists()


def test_delete_only_with_delete(client, contacts):
    r = client.get(reverse("contacts:delete", args=[contacts[0].pk]), **HTMX)
    assert r.status_code == 405


def test_csrf_rejects_post_without_token(contacts):
    c = Client(enforce_csrf_checks=True)
    r = c.delete(reverse("contacts:delete", args=[contacts[0].pk]), **HTMX)
    assert r.status_code == 403


def test_csrf_accepts_the_token_in_the_header(contacts):
    c = Client(enforce_csrf_checks=True)
    page = c.get(reverse("contacts:list"))
    token = page.cookies["csrftoken"].value
    r = c.delete(reverse("contacts:delete", args=[contacts[0].pk]), **HTMX, HTTP_X_CSRFTOKEN=token)
    assert r.status_code == 200


def test_cancel_edit_returns_the_original_row(client, contacts):
    c = contacts[0]
    r = client.get(reverse("contacts:row", args=[c.pk]), **HTMX)
    assert "Person 00" in r.text and "<form" not in r.text
