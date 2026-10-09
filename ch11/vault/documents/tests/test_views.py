"""The views, from the web: the services were already tested, but not that the right button calls them."""

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from documents import rag, services
from documents.models import Access, Document

from .conftest import SEQ, text_file


@pytest.fixture
def logged_in(client):
    def _login(user):
        client.force_login(user)
        return client

    return _login


def messages_of(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


def test_the_owner_grants_an_access_from_the_page(logged_in, doc, marta, luca):
    response = logged_in(marta).post(reverse("grant_access", args=[doc.pk]), {"user": luca.pk, "level": 2})
    assert response.status_code == 302
    assert Access.objects.get(document=doc, user=luca).level == Access.Level.EDIT


def test_only_the_owner_can_grant_an_access(logged_in, doc, marta, luca, giulia, grant):
    grant(doc, luca, Access.Level.EDIT)
    response = logged_in(luca).post(reverse("grant_access", args=[doc.pk]), {"user": giulia.pk, "level": 1})
    assert response.status_code == 403
    assert not Access.objects.filter(document=doc, user=giulia).exists()


def test_the_owner_revokes_an_access_from_the_page(logged_in, doc, marta, luca, grant):
    grant(doc, luca)
    response = logged_in(marta).post(reverse("revoke_access", args=[doc.pk, luca.pk]))
    assert response.status_code == 302
    assert not Access.objects.filter(document=doc, user=luca).exists()


def test_revoking_an_access_touches_only_that_document(logged_in, doc, marta, luca, grant):
    other = services.create_document(marta, "Another document", text_file("Something else."))
    grant(doc, luca)
    grant(other, luca)
    logged_in(marta).post(reverse("revoke_access", args=[doc.pk, luca.pk]))
    assert not Access.objects.filter(document=doc, user=luca).exists()
    assert Access.objects.filter(document=other, user=luca).exists()


def test_revoking_the_access_of_a_reviewer_shows_the_reason_and_changes_nothing(logged_in, doc, marta, luca):
    services.send_for_review(marta, doc, [luca], SEQ)
    response = logged_in(marta).post(reverse("revoke_access", args=[doc.pk, luca.pk]))
    assert "cancel it first" in messages_of(response)[0]
    assert Access.objects.filter(document=doc, user=luca).exists()


def test_a_new_version_is_uploaded_from_the_page(logged_in, doc, marta):
    response = logged_in(marta).post(
        reverse("new_version", args=[doc.pk]), {"file": text_file("Twenty-eight days."), "note": "More vacation"}
    )
    assert response.status_code == 302
    assert doc.versions.count() == 2
    assert doc.versions.first().note == "More vacation"  # the note typed in the form is not lost


def test_an_identical_file_shows_an_error_and_creates_no_version(logged_in, doc, marta):
    response = logged_in(marta).post(
        reverse("new_version", args=[doc.pk]), {"file": text_file("Twenty-six days of paid vacation.")}
    )
    assert "identical" in messages_of(response)[0]
    assert doc.versions.count() == 1


def test_the_owner_cancels_a_review_from_the_page(logged_in, doc, marta, luca):
    services.send_for_review(marta, doc, [luca], SEQ)
    logged_in(marta).post(reverse("cancel_review", args=[doc.pk]))
    doc.refresh_from_db()
    assert doc.state == Document.State.DRAFT


def test_someone_who_is_not_a_reviewer_cannot_decide(logged_in, doc, marta, luca, giulia, grant):
    services.send_for_review(marta, doc, [luca], SEQ)
    grant(doc, giulia)
    response = logged_in(giulia).post(reverse("decide", args=[doc.pk]), {"decision": "approve"})
    assert response.status_code == 403


def test_an_unknown_version_number_is_a_404(logged_in, doc, marta):
    assert logged_in(marta).get(reverse("download", args=[doc.pk, 99])).status_code == 404


def test_search_without_a_question_shows_just_the_form(logged_in, marta):
    page = logged_in(marta).get(reverse("search"))
    assert page.status_code == 200 and rag.NOT_FOUND not in page.text


def test_a_question_with_nothing_to_find_gets_the_honest_answer(logged_in, marta):
    page = logged_in(marta).get(reverse("search"), {"q": "anything at all"})
    assert rag.NOT_FOUND in page.text
