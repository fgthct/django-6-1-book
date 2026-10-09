import uuid

import pytest
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db.models.signals import post_delete

from knowledge.models import Chunk, Document


@pytest.fixture
def doc(db):
    d = Document.objects.create(path="x.md", title="X", hash="h")
    for i in range(3):
        Chunk.objects.create(document=d, position=i, text=f"chunk number {i}")
    return d


def test_the_id_is_a_uuid_generated_by_the_database(db):
    d = Document.objects.create(path="x.md", title="X", hash="h")
    d.refresh_from_db()
    assert isinstance(d.pk, uuid.UUID)


def test_the_id_is_a_uuid_version_7(db):
    d = Document.objects.create(path="x.md", title="X", hash="h")
    d.refresh_from_db()
    assert d.pk.version == 7


def test_ids_grow_with_time(db):
    ids = [Document.objects.create(path=f"{i}.md", title="T", hash="h") for i in range(5)]
    for d in ids:
        d.refresh_from_db()
    assert [d.pk for d in ids] == sorted(d.pk for d in ids)


def test_the_default_of_the_id_is_in_the_database_not_in_python(db):
    with connection.cursor() as c:
        c.execute(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_name = 'knowledge_document' AND column_name = 'id'"
        )
        assert "uuidv7" in c.fetchone()[0].lower()


def test_deleting_a_document_deletes_its_chunks(doc):
    doc.delete()
    assert Chunk.objects.count() == 0


def test_the_cascade_is_done_by_the_database_not_by_django(doc):
    received = []

    def receiver(sender, **kwargs):
        received.append(sender)

    post_delete.connect(receiver, weak=False)
    try:
        doc.delete()
    finally:
        post_delete.disconnect(receiver)
    assert received == [Document]  # no signal for Chunk: Django never saw those rows


def test_the_foreign_key_has_on_delete_cascade_in_the_database(db):
    with connection.cursor() as c:
        c.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid = 'knowledge_chunk'::regclass AND contype = 'f'"
        )
        assert "ON DELETE CASCADE" in c.fetchone()[0]


def test_two_chunks_cannot_have_the_same_position(doc):
    with pytest.raises(IntegrityError), transaction.atomic():
        Chunk.objects.create(document=doc, position=0, text="duplicate")


def test_the_search_column_is_computed_by_the_database(db):
    d = Document.objects.create(path="y.md", title="Y", hash="h")
    c = Chunk.objects.create(document=d, position=0, section="Illness", text="Send the certificate.")
    c.refresh_from_db()
    assert "certif" in c.search and "ill" in c.search  # stemmed lexemes


def test_the_search_column_follows_the_text(db):
    d = Document.objects.create(path="y.md", title="Y", hash="h")
    c = Chunk.objects.create(document=d, position=0, text="apples")
    Chunk.objects.filter(pk=c.pk).update(text="bananas")
    c.refresh_from_db()
    assert "banana" in c.search and "appl" not in c.search


def test_models_and_migrations_are_aligned(db):
    # An index is defined by the migration, not by the model: if someone changes
    # the model without creating the migration, the database stays as it was
    # and no other test notices.
    call_command("makemigrations", "--check", "--dry-run", verbosity=0)
