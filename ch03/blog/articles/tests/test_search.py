from django.contrib.postgres.search import Lexeme, SearchQuery

from articles.models import Article

from .helpers import search, slugs


def test_english_stemming_finds_inflected_forms(articles):
    # the text says "climbed", the search says "climbing"
    assert "etna" in slugs(search("climbing"))


def test_the_draft_appears_in_the_raw_search(articles):
    raw = Article.objects.filter(search=SearchQuery("cannolo", config="english"))
    assert "draft" in slugs(raw)


def test_the_title_weighs_more_than_the_body(articles):
    assert slugs(search("etna"))[0] == "etna"


def test_exclusion_operator(articles):
    results = slugs(search("etna -cable"))
    assert "etna" not in results
    assert "castle" in results


def test_exact_phrase(articles):
    assert slugs(search('"greek theater"')) == ["theater"]


def test_stemmer_sicily_and_sicilian_do_not_match(articles):
    assert "etna" in slugs(search("sicily"))
    assert "etna" not in slugs(search("sicilian"))


def test_the_prefix_solves_the_stemmer_limit(articles):
    query = SearchQuery(Lexeme("sicil", prefix=True), config="english", search_type="raw")
    found = slugs(Article.objects.filter(search=query))
    assert {"etna", "arancino"} <= set(found)


def test_the_ranked_search_is_deterministic(articles):
    assert search("etna").totally_ordered is True
