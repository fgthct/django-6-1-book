import os

import pytest
from django.conf import settings
from django.core.management import call_command
from django.db import DataError, connection, transaction
from pgvector.django import CosineDistance, L2Distance

from sentences import embedder
from sentences.models import SamplePoint, Sentence
from sentences.search import search_by_meaning, search_by_words


def vector(x, y):
    """A vector of the right size, with two chosen coordinates and zeros for the rest."""
    return [x, y] + [0.0] * (settings.EMBEDDING_DIMENSIONS - 2)


@pytest.fixture
def hand_made(db):
    """Three sentences with vectors we chose: the test depends on no model."""
    return {
        "a": Sentence.objects.create(text="a: same direction, short", topic="t", embedding=vector(0.5, 0)),
        "b": Sentence.objects.create(text="b: very long and off", topic="t", embedding=vector(10, 2)),
        "c": Sentence.objects.create(text="c: almost the same", topic="t", embedding=vector(0.9, 0.1)),
    }


def test_the_order_is_by_cosine_distance(hand_made):
    order = [s.text[0] for s in search_by_meaning("x", vector=vector(1, 0))]
    # a points the same way as the question (even if it is short): it is the closest.
    # With L2 distance the order would be c, a, b; with the inner product, b, c, a.
    assert order == ["a", "c", "b"]


def test_the_distance_of_an_identical_vector_is_zero(hand_made):
    first = search_by_meaning("x", vector=vector(0.5, 0))[0]
    assert first.text.startswith("a") and first.distance == pytest.approx(0, abs=1e-6)


def test_sentences_without_an_embedding_are_left_out(hand_made):
    Sentence.objects.create(text="d: no vector yet", topic="t")
    assert len(list(search_by_meaning("x", limit=10, vector=vector(1, 0)))) == 3


def test_equal_distances_have_a_stable_order(db):
    first = Sentence.objects.create(text="first", topic="t", embedding=vector(1, 0))
    second = Sentence.objects.create(text="second", topic="t", embedding=vector(2, 0))  # same direction
    result = [s.pk for s in search_by_meaning("x", vector=vector(1, 0))]
    assert result == [first.pk, second.pk]


def test_the_limit_is_respected(hand_made):
    assert len(list(search_by_meaning("x", limit=2, vector=vector(1, 0)))) == 2


def test_word_search_only_returns_sentences_containing_the_terms(db):
    Sentence.objects.create(text="Volcanoes and eruptions", topic="v")
    Sentence.objects.create(text="Volcanoes and wine", topic="v")
    Sentence.objects.create(text="Pasta and tomato", topic="c")
    assert [s.text for s in search_by_words("eruptions")] == ["Volcanoes and eruptions"]
    assert list(search_by_words("mountain of fire")) == []


def test_the_hnsw_index_serves_cosine_distance_and_not_l2(db):
    SamplePoint.objects.create(group=1, embedding=vector(1, 0))

    def plan(expression):
        with connection.cursor() as c:
            c.execute("SET enable_seqscan = off")
            sql, params = SamplePoint.objects.order_by(expression)[:3].query.sql_with_params()
            c.execute("EXPLAIN " + sql, params)
            return "\n".join(r[0] for r in c.fetchall())

    assert "samplepoint_hnsw" in plan(CosineDistance("embedding", vector(1, 0)))
    assert "samplepoint_hnsw" not in plan(L2Distance("embedding", vector(1, 0)))


def test_models_and_migrations_are_aligned(db):
    # An index is defined by the migration, not by the model: if someone changes
    # the model (say, the index operator) without creating the migration,
    # the database stays as it was and no other test notices.
    call_command("makemigrations", "--check", "--dry-run")


def test_the_database_rejects_a_vector_of_the_wrong_size(db):
    with pytest.raises(DataError), transaction.atomic():
        SamplePoint.objects.create(group=1, embedding=[0.1] * 384)


def test_embed_rejects_a_model_with_the_wrong_dimensions(monkeypatch):
    class FakeArray(list):
        def tolist(self):
            return list(self)

    class FakeModel:
        def embed(self, texts):
            return [FakeArray([0.0] * 384) for _ in texts]

    monkeypatch.setattr(embedder, "_model", lambda: FakeModel())
    with pytest.raises(ValueError, match="384 dimensions"):
        embedder.embed(["hello"])


@pytest.fixture
def fake_embed(monkeypatch):
    calls = []

    def fake(texts):
        calls.append(list(texts))
        return [vector(1, 0) for _ in texts]

    monkeypatch.setattr("sentences.management.commands.load_sentences.embed", fake)
    return calls


def test_load_sentences_computes_all_the_embeddings_once(db, fake_embed):
    call_command("load_sentences")
    assert Sentence.objects.count() == 40
    assert Sentence.objects.filter(embedding=None).count() == 0
    assert len(fake_embed) == 1 and len(fake_embed[0]) == 40  # one call, in bulk


def test_load_sentences_is_idempotent(db, fake_embed):
    call_command("load_sentences")
    call_command("load_sentences")
    assert Sentence.objects.count() == 40
    assert len(fake_embed) == 1  # the second run had nothing to do


@pytest.mark.skipif(not os.environ.get("TEST_MODEL"), reason="uses the real model: set TEST_MODEL=1")
def test_with_the_real_model_suppli_is_closer_to_arancini_than_to_the_stock_exchange(db):
    call_command("load_sentences")
    result = {s.text: s.distance for s in search_by_meaning("Roman supplì", limit=40)}
    assert result["How to make Sicilian arancini with ragù and peas"] < result[
        "The Milan stock exchange closes higher on bank shares"
    ]


def test_the_search_command_shows_both_rankings(hand_made, monkeypatch, capsys):
    monkeypatch.setattr("sentences.search.embed", lambda texts: [vector(1, 0)])
    call_command("search", "almost the same", "--compare")
    out = capsys.readouterr().out
    assert "By meaning (cosine distance):" in out
    assert out.index("a: same direction") < out.index("c: almost the same")  # by meaning: a is closer
    assert "[t] c: almost the same" in out.split("By words")[1]  # by words: only c contains the terms


def test_the_ordering_of_the_search_is_total(db):
    # With little data, ties come out in a stable order by chance and a test on the
    # results would not notice: we ask Django whether the ordering is deterministic.
    assert search_by_meaning("x", vector=vector(1, 0)).totally_ordered
