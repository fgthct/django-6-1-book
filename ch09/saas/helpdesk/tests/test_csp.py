import json
import re

import pytest
from django.test import Client
from django.urls import reverse

from helpdesk.models import CspViolation

from .conftest import client_web


def policy(response):
    return response.headers["Content-Security-Policy"]


def test_every_response_has_the_policy(acme, admin_acme):
    web = client_web(acme, admin_acme)
    for path in ("/dashboard/", "/login/", "/counters/"):
        assert "Content-Security-Policy" in web.get(path).headers


def test_no_unsafe_inline_and_no_unsafe_eval(acme, admin_acme):
    header = policy(client_web(acme, admin_acme).get("/dashboard/"))
    assert "unsafe-inline" not in header
    assert "unsafe-eval" not in header


def test_nobody_can_frame_us(acme, admin_acme):
    assert "frame-ancestors 'none'" in policy(client_web(acme, admin_acme).get("/dashboard/"))


def test_the_nonce_changes_on_every_request_and_matches_the_script(acme, admin_acme):
    client = client_web(acme, admin_acme)
    seen = []
    for _ in range(2):
        response = client.get(reverse("dashboard"))
        in_header = re.search(r"script-src [^;]*'nonce-([^']+)'", response["Content-Security-Policy"]).group(1)
        in_page = re.search(r'<script nonce="([^"]+)"', response.text).group(1)
        assert in_header == in_page
        seen.append(in_header)
    assert seen[0] != seen[1]


def test_the_candidate_policy_only_reports(acme, admin_acme):
    response = client_web(acme, admin_acme).get("/dashboard/")
    assert "Content-Security-Policy-Report-Only" in response.headers
    assert "require-trusted-types-for" in response.headers["Content-Security-Policy-Report-Only"]
    assert "require-trusted-types-for" not in policy(response)


@pytest.mark.parametrize("path", ["/dashboard/", "/login/"])
def test_the_pages_have_no_inline_scripts_styles_or_handlers(acme, admin_acme, path):
    html = client_web(acme, admin_acme).get(path).text
    assert not re.search(r"<script(?![^>]*\bsrc=)(?![^>]*\bnonce=)", html)
    assert "<style" not in html
    assert not re.search(r"\son(click|load|error|submit)=", html)
    assert " style=" not in html


def test_the_ticket_page_has_no_inline_handlers_either(acme, admin_acme, ticket_acme):
    html = client_web(acme, admin_acme).get(f"/tickets/{ticket_acme.pk}/").text
    assert not re.search(r"\son(click|load|error|submit)=", html)


def post_report(client, payload, **kwargs):
    body = payload if isinstance(payload, (bytes, str)) else json.dumps(payload)
    return client.post("/csp-report/", body, content_type="application/csp-report", **kwargs)


def test_the_report_endpoint_works_without_csrf(acme):
    client = Client(enforce_csrf_checks=True, HTTP_HOST="acme.localhost")
    payload = {"csp-report": {"effective-directive": "script-src-elem", "blocked-uri": "inline",
                              "document-uri": "http://acme.localhost/dashboard/"}}
    assert post_report(client, payload).status_code == 204
    violation = CspViolation.objects.get()
    assert (violation.directive, violation.blocked_resource) == ("script-src-elem", "inline")
    assert violation.host == "acme.localhost"
    assert violation.report_only is False


def test_the_new_reporting_api_format_is_understood_too(acme):
    client = Client(enforce_csrf_checks=True, HTTP_HOST="acme.localhost")
    payload = [{"type": "csp-violation", "body": {"effectiveDirective": "img-src", "blockedURL": "https://x.test/a.png",
                                                     "documentURL": "http://acme.localhost/", "disposition": "report"}}]
    assert post_report(client, payload).status_code == 204
    violation = CspViolation.objects.get()
    assert violation.directive == "img-src"
    assert violation.report_only is True


def test_a_huge_body_is_refused(db):
    assert post_report(Client(), "x" * 16_001).status_code == 413


def test_a_malformed_body_is_a_400(db):
    assert post_report(Client(), "not json").status_code == 400


def test_the_fields_are_truncated(db):
    post_report(Client(), {"csp-report": {"effective-directive": "d" * 500, "blocked-uri": "b" * 2000,
                                          "document-uri": "u" * 2000}})
    violation = CspViolation.objects.get()
    assert len(violation.directive) == 100
    assert len(violation.blocked_resource) == 500
    assert len(violation.document) == 500


def test_at_most_20_reports_are_saved_per_request(db):
    payload = [{"body": {"effectiveDirective": "img-src"}} for _ in range(50)]
    post_report(Client(), payload)
    assert CspViolation.objects.count() == 20


def test_only_post_is_accepted(db):
    assert Client().get("/csp-report/").status_code == 405
