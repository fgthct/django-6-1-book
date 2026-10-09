import pytest
from django.conf import settings
from django.core.management import call_command

from knowledge.models import Chunk, Document


def run(folder, *args):
    from io import StringIO

    out = StringIO()
    call_command("import_docs", str(folder), *args, stdout=out)
    return out.getvalue().strip()


def test_the_first_import_creates_everything(db, docs_folder):
    assert run(docs_folder) == "2 new, 0 updated, 0 unchanged"
    assert Document.objects.count() == 2 and Chunk.objects.count() == 2


def test_the_second_import_does_nothing(db, docs_folder):
    run(docs_folder)
    ids = set(Chunk.objects.values_list("pk", flat=True))
    assert run(docs_folder) == "0 new, 0 updated, 2 unchanged"
    assert set(Chunk.objects.values_list("pk", flat=True)) == ids  # the identifiers don't change


def test_only_the_modified_document_is_redone(db, docs_folder):
    run(docs_folder)
    before = {c.document.path: c.pk for c in Chunk.objects.select_related("document")}
    (docs_folder / "a.md").write_text("# Alpha\n\n## One\n\nNow about avocados.\n", encoding="utf-8")
    assert run(docs_folder) == "0 new, 1 updated, 1 unchanged"
    after = {c.document.path: c.pk for c in Chunk.objects.select_related("document")}
    assert after["b.md"] == before["b.md"]
    assert after["a.md"] != before["a.md"]
    assert "avocados" in Chunk.objects.get(document__path="a.md").text


def test_a_change_of_model_makes_everything_to_be_redone(db, docs_folder, settings):
    run(docs_folder)
    settings.EMBEDDING_MODEL = "another/model"
    assert run(docs_folder) == "0 new, 2 updated, 0 unchanged"
    assert set(Chunk.objects.values_list("model", flat=True)) == {"another/model"}


def test_force_redoes_everything(db, docs_folder):
    run(docs_folder)
    assert run(docs_folder, "--force") == "0 new, 2 updated, 0 unchanged"


def test_every_chunk_records_the_model_that_produced_its_vector(db, docs_folder):
    run(docs_folder)
    assert set(Chunk.objects.values_list("model", flat=True)) == {settings.EMBEDDING_MODEL}


def test_the_vectors_have_the_expected_size(db, docs_folder):
    run(docs_folder)
    assert all(len(c.embedding) == settings.EMBEDDING_DIMENSIONS for c in Chunk.objects.all())


def test_a_document_that_disappeared_is_kept_by_default(db, docs_folder):
    run(docs_folder)
    (docs_folder / "b.md").unlink()
    run(docs_folder)
    assert Document.objects.filter(path="b.md").exists()


def test_orphans_are_deleted_only_if_asked(db, docs_folder):
    run(docs_folder)
    (docs_folder / "b.md").unlink()
    out = run(docs_folder, "--delete-orphans")
    assert "1 orphan documents deleted" in out
    assert not Document.objects.filter(path="b.md").exists()
    assert Chunk.objects.count() == 1


def test_a_failure_during_the_insert_leaves_the_old_content_intact(db, docs_folder, monkeypatch):
    run(docs_folder)
    old = list(Chunk.objects.filter(document__path="a.md").values_list("pk", "text"))
    (docs_folder / "a.md").write_text("# Alpha\n\n## One\n\nNew text.\n", encoding="utf-8")

    def boom(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(Chunk.objects, "bulk_create", boom)
    with pytest.raises(RuntimeError):
        run(docs_folder)
    assert list(Chunk.objects.filter(document__path="a.md").values_list("pk", "text")) == old


def test_a_failure_of_the_model_does_not_touch_the_database(db, docs_folder, monkeypatch):
    run(docs_folder)
    (docs_folder / "a.md").write_text("# Alpha\n\n## One\n\nNew text.\n", encoding="utf-8")
    monkeypatch.setattr("knowledge.management.commands.import_docs.embed", lambda texts: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        run(docs_folder)
    assert "apples" in Chunk.objects.get(document__path="a.md").text


def test_the_title_comes_from_the_document(db, docs_folder):
    run(docs_folder)
    assert Document.objects.get(path="a.md").title == "Alpha"


def test_the_embedder_refuses_a_model_with_the_wrong_dimensions(monkeypatch):
    from knowledge import embedder

    class FakeArray(list):
        def tolist(self):
            return list(self)

    class WrongModel:
        def embed(self, texts):
            return [FakeArray([0.0] * 384) for _ in texts]

    monkeypatch.setattr(embedder, "_model", lambda: WrongModel())
    with pytest.raises(ValueError, match="384 dimensions"):
        embedder.embed(["hello"])
