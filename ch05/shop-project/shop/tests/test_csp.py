import re

from django.urls import reverse


def test_the_page_carries_a_csp_with_nonce(client, catalog):
    r = client.get(reverse("shop:catalog"))
    policy = r["Content-Security-Policy"]
    nonce = re.search(r"'nonce-([^']+)'", policy).group(1)
    assert f'<script nonce="{nonce}">' in r.text


def test_the_nonce_changes_on_every_response(client, catalog):
    nonces = {
        re.search(r"'nonce-([^']+)'", client.get(reverse("shop:catalog"))["Content-Security-Policy"]).group(1)
        for _ in range(3)
    }
    assert len(nonces) == 3


def test_the_policy_allows_no_inline_code_or_styles(client, catalog):
    policy = client.get(reverse("shop:catalog"))["Content-Security-Policy"]
    assert "'unsafe-inline'" not in policy and "'unsafe-eval'" not in policy
    assert policy.startswith("default-src 'none'")


def test_pages_have_no_inline_styles_or_handlers(client, catalog):
    for url in (reverse("shop:catalog"), reverse("shop:cart")):
        html = client.get(url).text
        assert "<style" not in html
        assert not re.search(r'\sstyle=|\sonclick=|\sonload=', html)
