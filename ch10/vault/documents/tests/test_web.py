import re
from pathlib import Path

import pytest
from config import settings as project_settings
from django.urls import reverse

from documents import services
from documents.models import Access

from .conftest import FREE, SEQ, text_file

HTMX = {"HX-Request": "true"}


@pytest.fixture
def logged_in(client):
    def _login(user):
        client.force_login(user)
        return client

    return _login


def test_anonymous_users_are_sent_to_the_login(client, doc):
    for url in (reverse("list"), reverse("detail", args=[doc.pk]), reverse("search")):
        response = client.get(url)
        assert response.status_code == 302 and response.url.startswith("/login/")


def test_the_list_shows_the_users_documents(logged_in, doc, marta):
    page = logged_in(marta).get(reverse("list"))
    assert page.status_code == 200 and "Vacation policy" in page.text


def test_uploading_a_file_creates_the_document(logged_in, marta):
    response = logged_in(marta).post(reverse("create"), {"title": "Minutes", "file": text_file("We met.")})
    assert response.status_code == 302
    assert marta.documents.get().current_version.text == "We met."


def test_a_binary_upload_shows_an_error_and_creates_nothing(logged_in, marta):
    client = logged_in(marta)
    client.post(reverse("create"), {"file": text_file(b"\xff\xfe", "photo.png")})
    assert marta.documents.count() == 0
    assert "Only UTF-8 text files" in client.get(reverse("list")).text


def test_the_download_is_an_attachment(logged_in, doc, marta):
    response = logged_in(marta).get(reverse("download", args=[doc.pk, 1]))
    assert response["Content-Disposition"].startswith("attachment")
    assert b"".join(response.streaming_content) == b"Twenty-six days of paid vacation."


def test_an_imported_version_without_a_file_is_generated_from_its_text(logged_in, doc, marta):
    version = doc.current_version
    version.file = ""
    version.save()
    response = logged_in(marta).get(reverse("download", args=[doc.pk, 1]))
    assert response.content == b"Twenty-six days of paid vacation."
    assert response["Content-Disposition"].startswith("attachment")


def test_no_url_serves_the_uploaded_files(client, doc):
    assert not hasattr(project_settings, "MEDIA_URL")  # MEDIA_ROOT yes, MEDIA_URL no
    path = doc.current_version.file.name
    assert client.get(f"/media/{path}").status_code == 404
    assert client.get(f"/{path}").status_code == 404


# --- the flow, with and without HTMX ------------------------------------------------------------

def send(client, doc, luca_pk, giulia_pk, mode="sequential", message="Please read it."):
    return client.post(
        reverse("send_for_review", args=[doc.pk]),
        {"reviewer_1": luca_pk, "reviewer_2": giulia_pk, "mode": mode, "message": message},
        headers=HTMX,
    )


def test_an_htmx_action_returns_only_the_flow_fragment(logged_in, doc, marta, luca, giulia):
    response = send(logged_in(marta), doc, luca.pk, giulia.pk)
    assert response.status_code == 200
    assert "<html" not in response.text and 'id="flow"' in response.text
    assert "In review" in response.text and "Luca Neri" in response.text


def test_without_htmx_the_same_action_redirects(logged_in, doc, marta, luca):
    response = logged_in(marta).post(reverse("send_for_review", args=[doc.pk]), {"reviewer_1": luca.pk, "mode": "free"})
    assert response.status_code == 302 and response.url == reverse("detail", args=[doc.pk])


def test_a_refusal_by_a_rule_appears_inside_the_htmx_fragment(logged_in, doc, marta, luca, giulia):
    services.send_for_review(marta, doc, [luca, giulia], SEQ)
    response = logged_in(giulia).post(reverse("decide", args=[doc.pk]), {"decision": "approve"}, headers=HTMX)
    assert response.status_code == 200
    assert "It is not your turn yet." in response.text


def test_that_error_does_not_come_back_in_the_next_page(logged_in, doc, marta, luca, giulia):
    services.send_for_review(marta, doc, [luca, giulia], SEQ)
    client = logged_in(giulia)
    client.post(reverse("decide", args=[doc.pk]), {"decision": "approve"}, headers=HTMX)
    assert "It is not your turn yet." not in client.get(reverse("detail", args=[doc.pk])).text


def test_only_the_reviewer_whose_turn_it_is_sees_the_approve_button(logged_in, doc, marta, luca, giulia):
    services.send_for_review(marta, doc, [luca, giulia], SEQ, "Check page two.")
    page = logged_in(luca).get(reverse("detail", args=[doc.pk])).text
    assert "Check page two." in page and ">Approve<" in page
    assert ">Approve<" not in logged_in(giulia).get(reverse("detail", args=[doc.pk])).text
    assert ">Approve<" not in logged_in(marta).get(reverse("detail", args=[doc.pk])).text


def test_in_free_mode_both_reviewers_see_the_button(logged_in, doc, marta, luca, giulia):
    services.send_for_review(marta, doc, [luca, giulia], FREE)
    for user in (luca, giulia):
        assert ">Approve<" in logged_in(user).get(reverse("detail", args=[doc.pk])).text


def test_the_owner_is_not_offered_in_the_reviewer_menu(logged_in, doc, marta, luca):
    page = logged_in(marta).get(reverse("detail", args=[doc.pk])).text
    menu = page[page.index('name="reviewer_1"'):page.index('name="reviewer_2"')]
    assert "Luca Neri" in menu and "Marta Bianchi" not in menu


def test_only_the_owner_sees_the_access_management(logged_in, doc, marta, luca, grant):
    grant(doc, luca, Access.Level.EDIT)
    assert "Revoke" not in logged_in(luca).get(reverse("detail", args=[doc.pk])).text
    assert 'name="level"' in logged_in(marta).get(reverse("detail", args=[doc.pk])).text


# --- escaping, CSP and the dark theme -----------------------------------------------------------

def test_what_the_user_writes_is_escaped(logged_in, marta):
    client = logged_in(marta)
    content = "<img src=x onerror=alert(2)> and more"
    response = client.post(reverse("create"), {"title": "<script>alert(1)</script>", "file": text_file(content)})
    page = client.get(response.url).text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<script>alert(1)" not in page
    assert "&lt;img src=x onerror=alert(2)&gt;" in page
    assert "<img src=x" not in page


def test_every_page_carries_the_csp_and_a_nonce_that_matches(logged_in, doc, marta):
    client = logged_in(marta)
    for url in (reverse("list"), reverse("detail", args=[doc.pk])):
        response = client.get(url)
        header = response["Content-Security-Policy"]
        assert "unsafe-inline" not in header and "unsafe-eval" not in header
        nonce = re.search(r"script-src [^;]*'nonce-([^']+)'", header).group(1)
        assert f'<script nonce="{nonce}">' in response.text


def test_the_pages_have_no_inline_scripts_styles_or_handlers(logged_in, doc, marta):
    html = logged_in(marta).get(reverse("detail", args=[doc.pk])).text
    assert not re.search(r"<script(?![^>]*\bsrc=)(?![^>]*\bnonce=)", html)
    assert "<style" not in html and " style=" not in html
    assert not re.search(r"\son(click|load|error|submit|change)=", html)


def test_the_page_declares_the_dark_scheme_to_the_browser(logged_in, marta):
    html = logged_in(marta).get(reverse("list")).text
    assert '<meta name="color-scheme" content="dark">' in html


CSS = Path(__file__).resolve().parents[2] / "static" / "app.css"


def test_the_stylesheet_declares_the_dark_scheme():
    assert re.search(r":root\s*{[^}]*color-scheme:\s*dark", CSS.read_text())


def test_no_white_background_anywhere_in_the_stylesheet():
    css = CSS.read_text()
    for value in re.findall(r"background(?:-color)?\s*:\s*([^;}]+)", css):
        assert not re.search(r"#fff(?:fff)?\b|\bwhite\b|rgb\(\s*255", value, re.I), value


def test_search_finds_a_document_through_the_page(logged_in, marta, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        services.create_document(marta, "Vacation policy", text_file("Employees have twenty-six days of paid vacation."))
    page = logged_in(marta).get(reverse("search"), {"q": "days of paid vacation"})
    assert "twenty-six days" in page.text and "Vacation policy" in page.text
