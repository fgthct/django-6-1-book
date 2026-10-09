import pytest
from django.contrib.postgres.search import SearchQuery
from django.db import connection

from knowledge.models import Chunk
from knowledge.search import (
    hybrid_search,
    rrf_fusion,
    search_by_meaning,
    search_by_words,
)


def test_meaning_search_puts_the_closest_chunk_first(corpus):
    best = search_by_meaning("vacation days per year", 3)[0]
    assert best.document.title == "Vacation and Leave"


def test_meaning_search_is_ordered_by_distance(corpus):
    distances = [c.distance for c in search_by_meaning("backup schedule", 10)]
    assert distances == sorted(distances)


def test_meaning_search_respects_the_limit(corpus):
    assert len(list(search_by_meaning("backup", 3))) == 3


def test_meaning_search_accepts_a_ready_made_vector(corpus):
    chunk = Chunk.objects.first()
    found = search_by_meaning("ignored", 1, vector=list(chunk.embedding))[0]
    assert found.pk == chunk.pk and found.distance == pytest.approx(0, abs=1e-5)


def test_chunks_without_a_vector_are_not_returned(corpus):
    Chunk.objects.filter(document__title="Backup and Restore").update(embedding=None)
    titles = {c.document.title for c in search_by_meaning("backup", 50)}
    assert "Backup and Restore" not in titles


@pytest.mark.parametrize(
    "settings_sql",
    ["SET LOCAL enable_seqscan = off", "SET LOCAL enable_indexscan = off; SET LOCAL enable_bitmapscan = off"],
    ids=["with index", "without index"],
)
def test_chunks_without_an_embedding_never_appear_with_any_plan(corpus, settings_sql):
    """The HNSW index skips the NULLs by itself, the sequential scan does not.

    Without `exclude(embedding=None)` the result would depend on the plan chosen
    by PostgreSQL, that is, on the table statistics: a bug that comes and goes.
    Here we force both plans.
    """
    from django.db import connection
    from knowledge.models import Chunk

    Chunk.objects.update(embedding=None)
    with connection.cursor() as c:
        c.execute(settings_sql)
    assert list(search_by_meaning("vacation", 5)) == []


def test_word_search_finds_the_chunks_that_contain_the_words(corpus):
    found = list(search_by_words("form RS-12", 5, all_words=True))
    assert found and "RS-12" in found[0].text


def test_word_search_in_and_finds_nothing_for_a_natural_question(corpus):
    assert list(search_by_words("How many vacation days do I get in a year?", 5, all_words=True)) == []


def test_word_search_in_or_finds_something_for_a_natural_question(corpus):
    found = list(search_by_words("How many vacation days do I get in a year?", 5))
    assert found and found[0].document.title == "Vacation and Leave"


def test_word_search_only_returns_chunks_that_match(corpus):
    assert list(search_by_words("zzzxyz", 5)) == []


def test_word_search_uses_the_english_configuration_explicitly(corpus):
    # A plain string uses the server's default configuration, which may be
    # different from the one used to build the column.
    with_config = Chunk.objects.filter(search=SearchQuery("vacations", config="english")).count()
    assert with_config > 0
    found = list(search_by_words("vacations", 5, all_words=True))
    assert len(found) == with_config


def test_rrf_sums_the_contributions_of_the_two_rankings():
    result = dict(rrf_fusion([["a", "b", "c"], ["c", "b"]]))
    assert result["c"] == pytest.approx(1 / 63 + 1 / 61)
    assert result["b"] == pytest.approx(1 / 62 + 1 / 62)
    assert result["a"] == pytest.approx(1 / 61)


def test_rrf_agreement_beats_an_isolated_first_place():
    # "x" is first in one list only; "y" is third and fifth: it must win.
    first = ["x", "p", "y", "q", "r"]
    second = ["s", "t", "u", "v", "y"]
    ranked = [item for item, _ in rrf_fusion([first, second])]
    assert ranked.index("y") < ranked.index("x")


def test_rrf_is_ordered_from_the_best():
    ranked = rrf_fusion([["a", "b"], ["b", "a"], ["b"]])
    scores = [s for _, s in ranked]
    assert scores == sorted(scores, reverse=True)
    assert ranked[0][0] == "b"


def test_rrf_ties_keep_the_order_of_first_appearance():
    assert [i for i, _ in rrf_fusion([["a"], ["b"]])] == ["a", "b"]


def test_rrf_with_an_empty_ranking_is_the_other_ranking():
    assert [i for i, _ in rrf_fusion([["a", "b"], []])] == ["a", "b"]


def test_rrf_uses_the_constant_k():
    assert dict(rrf_fusion([["a"]], k=10))["a"] == pytest.approx(1 / 11)


def test_hybrid_search_remembers_the_position_in_each_ranking(corpus):
    results = hybrid_search("form RS-12", 3)
    top = results[0]
    assert "RS-12" in top.chunk.text
    assert top.meaning_position is not None and top.words_position == 1


def test_hybrid_search_with_and_is_quiet_when_the_words_find_nothing(corpus):
    results = hybrid_search("How many vacation days do I get in a year?", 5)
    assert all(r.words_position is None for r in results)


def test_hybrid_search_actually_uses_the_two_lists(corpus, monkeypatch):
    chunks = list(Chunk.objects.all()[:4])
    for c in chunks:
        c.distance = 0.1
        c.rank = 0.1
    monkeypatch.setattr("knowledge.search.search_by_meaning", lambda *a, **k: [chunks[0], chunks[1]])
    monkeypatch.setattr("knowledge.search.search_by_words", lambda *a, **k: [chunks[2], chunks[3]])
    results = hybrid_search("whatever", 4)
    assert {r.chunk.pk for r in results} == {c.pk for c in chunks}  # items from both lists
    assert [r.chunk.pk for r in results] == [chunks[0].pk, chunks[2].pk, chunks[1].pk, chunks[3].pk]


def test_hybrid_search_respects_the_limit(corpus):
    assert len(hybrid_search("vacation backup customer", 2)) == 2
