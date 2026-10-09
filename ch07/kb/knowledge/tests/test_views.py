import pytest
from django.urls import reverse

from knowledge.models import Chunk, Document


def test_the_home_page_has_the_form(client, db):
    r = client.get(reverse("index"))
    assert r.status_code == 200 and 'hx-get="/search/"' in r.text


def test_the_ask_button_includes_the_fields_of_the_form(client, db):
    # A button with its own hx-get inside a form does NOT include the form's fields
    # for a GET request, unless we say so.
    assert 'hx-include="closest form"' in client.get(reverse("index")).text


def test_the_search_view_returns_a_fragment_not_a_page(client, corpus):
    r = client.get(reverse("search"), {"q": "vacation days"})
    assert "<html" not in r.text and "<article>" in r.text


def test_a_partial_is_not_visible_in_the_whole_page(client, db):
    page = client.get(reverse("index")).text
    assert "Write a question." not in page and "Sources" not in page


def test_an_empty_question_asks_for_a_question(client, db):
    assert "Write a question." in client.get(reverse("search"), {"q": ""}).text
    assert "Write a question." in client.get(reverse("ask"), {"q": "  "}).text


def test_the_results_explain_why_they_came_out(client, corpus):
    text = client.get(reverse("search"), {"q": "form RS-12"}).text
    assert "by meaning:" in text and "by words:" in text


@pytest.mark.parametrize("mode", ["hybrid", "meaning", "words"])
def test_every_mode_works(client, corpus, mode):
    r = client.get(reverse("search"), {"q": "backup schedule", "mode": mode})
    assert r.status_code == 200 and "<article>" in r.text


def test_an_invalid_mode_falls_back_to_hybrid(client, corpus):
    text = client.get(reverse("search"), {"q": "form RS-12", "mode": "nonsense"}).text
    # hybrid shows both positions for the chunk that is in both lists; "words" would show "—" for meaning
    first = text.split("<article>")[1]
    assert "by meaning: 1" in first or "by meaning: 2" in first


def test_the_mode_words_has_no_meaning_position(client, corpus):
    text = client.get(reverse("search"), {"q": "form RS-12", "mode": "words"}).text
    assert "by meaning: —" in text


def test_a_query_without_results_says_so(client, corpus):
    text = client.get(reverse("search"), {"q": "zzzxyz", "mode": "words"}).text
    assert "No results for" in text


def test_the_text_of_the_documents_is_escaped(client, db):
    d = Document.objects.create(path="e.md", title="Evil", hash="h")
    Chunk.objects.create(document=d, position=0, text="evil <script>alert(1)</script> vacation",
                         embedding=[1.0] + [0.0] * 767)
    text = client.get(reverse("search"), {"q": "evil vacation", "mode": "words"}).text
    assert "<script>alert" not in text and "&lt;script&gt;" in text


def test_the_ask_view_shows_the_answer_and_the_sources(client, corpus, settings):
    settings.RAG_MAX_DISTANCE = 2.0
    text = client.get(reverse("ask"), {"q": "How many vacation days? 26 days of vacation"}).text
    assert "26 days" in text and "Sources" in text and "Vacation and Leave" in text


def test_the_ask_view_says_dont_know_without_sources(client, corpus, settings):
    settings.RAG_MAX_DISTANCE = 0.0
    text = client.get(reverse("ask"), {"q": "What is the capital of Australia?"}).text
    assert "I don&#x27;t know" in text and "Sources" not in text
