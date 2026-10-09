import math
import random

import pytest
from django.conf import settings as django_settings

from documents import chunking, rag, search, services
from documents.embedder import embed
from documents.models import Access, Chunk, Document, Version
from documents.tasks import index_version

from .conftest import text_file


@pytest.fixture
def indexed(django_capture_on_commit_callbacks):
    """Create a document and run the indexing that normally starts after the commit."""

    def _make(owner, title, content):
        with django_capture_on_commit_callbacks(execute=True):
            return services.create_document(owner, title, text_file(content))

    return _make


# --- chunking and the embedder -----------------------------------------------------------------

def test_the_chunks_are_at_most_800_characters_and_break_at_paragraphs():
    paragraphs = [f"Paragraph {n}. " + "word " * 40 for n in range(12)]
    passages = chunking.split("\n\n".join(paragraphs))
    assert all(len(p) <= 800 for p in passages)
    assert len(passages) > 1
    assert "\n\n".join(passages).replace("\n\n", " ").split() == " ".join(paragraphs).split()


def test_a_paragraph_that_is_too_long_is_cut_at_a_space():
    passages = chunking.split("lorem ipsum " * 200)
    assert len(passages) >= 3 and all(len(p) <= 800 for p in passages)
    assert {w for p in passages for w in p.split()} == {"lorem", "ipsum"}  # no word was cut in half


def test_an_empty_text_has_no_chunks():
    assert chunking.split("  \n\n  ") == []


def test_the_fake_embedder_gives_normalized_vectors_of_the_right_size():
    (vector,) = embed(["paid vacation days"])
    assert len(vector) == django_settings.EMBEDDING_DIMENSIONS
    assert math.isclose(sum(x * x for x in vector), 1.0)
    assert embed(["paid vacation days"]) == [vector]  # deterministic


# --- indexing ----------------------------------------------------------------------------------

def test_indexing_creates_the_chunks_of_the_version_after_the_commit(marta, indexed):
    doc = indexed(marta, "Policy", "First paragraph.\n\n" + "Second paragraph. " * 60)
    assert doc.current_version.chunks.count() >= 1
    assert all(c.embedding is not None for c in doc.current_version.chunks.all())


def test_indexing_twice_does_not_double_the_chunks(marta, indexed):
    doc = indexed(marta, "Policy", "Paragraph one.\n\nParagraph two.")
    before = doc.current_version.chunks.count()
    index_version.call(version_id=str(doc.current_version.pk))
    assert doc.current_version.chunks.count() == before


# --- search with permissions -------------------------------------------------------------------

def test_you_find_the_passages_of_your_own_documents(marta, indexed):
    indexed(marta, "Vacation policy", "Employees have twenty-six days of paid vacation each year.")
    results = search.search(marta, "how many days of paid vacation")
    assert results and results[0].version.document.title == "Vacation policy"


def test_nothing_leaks_to_someone_without_access(marta, paolo, indexed):
    indexed(marta, "Salaries", "The salary of the director is confidential: one hundred thousand euros.")
    assert search.search(paolo, "the salary of the director is confidential") == []


def test_granting_and_revoking_access_makes_the_result_appear_and_disappear(marta, luca, indexed):
    doc = indexed(marta, "Salaries", "The salary of the director is confidential: one hundred thousand euros.")
    question = "salary of the director confidential"
    assert search.search(luca, question) == []
    services.grant_access(marta, doc, luca, Access.Level.READ)
    assert len(search.search(luca, question)) == 1
    services.revoke_access(marta, doc, luca)
    assert search.search(luca, question) == []


def test_only_the_current_version_answers(marta, indexed, django_capture_on_commit_callbacks):
    doc = indexed(marta, "Policy", "Vacation is twenty days a year, according to the old rule.")
    with django_capture_on_commit_callbacks(execute=True):
        services.upload_version(marta, doc, text_file("Remote work is allowed two days a week."))
    results = search.search(marta, "vacation twenty days old rule")
    assert all("Remote work" in r.text for r in results)
    assert Chunk.objects.count() == 2  # the old version's chunks are still there, but they don't answer


def test_results_come_ordered_by_distance_and_are_limited(marta, indexed):
    for n in range(4):
        indexed(marta, f"Doc {n}", f"vacation days {' extra' * n} unrelated words here")
    results = search.search(marta, "vacation days", limit=3)
    assert len(results) == 3
    assert [r.distance for r in results] == sorted(r.distance for r in results)


def test_a_very_selective_filter_still_returns_the_results(marta, luca):
    """3,000 chunks, and Luca sees only ten of them.

    A confession: on a table this small the planner doesn't use the HNSW index, so this test
    passes even without the `iterative_scan` line. The experiment with 30,000 rows is the real check.
    """
    rng = random.Random(42)

    def random_vector():
        v = [rng.random() - 0.5 for _ in range(django_settings.EMBEDDING_DIMENSIONS)]
        norm = math.sqrt(sum(x * x for x in v))
        return [x / norm for x in v]

    def make(owner, title, n_chunks):
        doc = Document.objects.create(title=title, owner=owner)
        version = Version.objects.create(document=doc, number=1, file_name="x.txt", text="x", hash="0" * 64, author=owner)
        doc.current_version = version
        doc.save()
        Chunk.objects.bulk_create(
            Chunk(version=version, position=n, text=f"{title} {n}", embedding=random_vector())
            for n in range(1, n_chunks + 1)
        )
        return doc

    make(marta, "Everybody else", 2990)
    mine = make(luca, "Luca's", 10)
    results = search.search(luca, "anything", limit=5, vector=random_vector())
    assert len(results) == 5
    assert {r.version.document_id for r in results} == {mine.pk}


# --- the answer that doesn't invent ------------------------------------------------------------

def test_the_answer_cites_its_sources(marta, indexed):
    indexed(marta, "Vacation policy", "Employees have twenty-six days of paid vacation each year.")
    answer = rag.answer(marta, "how many days of paid vacation do employees have")
    assert "twenty-six days" in answer.text
    assert answer.sources[0].version.document.title == "Vacation policy"


def test_if_nothing_is_close_enough_it_says_so(marta, indexed):
    indexed(marta, "Vacation policy", "Employees have twenty-six days of paid vacation each year.")
    answer = rag.answer(marta, "quarterly revenue forecast spreadsheet")
    assert answer.text == rag.NOT_FOUND and answer.sources == []


def test_someone_without_access_gets_the_not_found_answer(marta, paolo, indexed):
    indexed(marta, "Vacation policy", "Employees have twenty-six days of paid vacation each year.")
    assert rag.answer(paolo, "how many days of paid vacation").text == rag.NOT_FOUND
