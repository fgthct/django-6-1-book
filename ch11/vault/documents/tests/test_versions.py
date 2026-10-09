import threading
from pathlib import Path

import pytest
from django.core.exceptions import PermissionDenied
from django.db import connections

from documents import services
from documents.models import Access, Document

from .conftest import FREE, SEQ, text_file


def stored_files(settings):
    return [p for p in Path(settings.MEDIA_ROOT).rglob("*") if p.is_file()]


def test_a_new_document_has_version_one_with_its_file(doc, settings):
    version = doc.current_version
    assert version.number == 1
    assert version.text == "Twenty-six days of paid vacation."
    assert version.file_name == "notes.txt"
    assert len(version.hash) == 64
    assert doc.state == Document.State.DRAFT
    assert len(stored_files(settings)) == 1


def test_a_new_version_gets_the_next_number_and_the_old_one_stays(doc, marta):
    services.upload_version(marta, doc, text_file("Twenty-eight days."), "revised")
    doc.refresh_from_db()
    assert doc.current_version.number == 2
    assert [v.number for v in doc.versions.all()] == [2, 1]
    assert doc.versions.get(number=1).text == "Twenty-six days of paid vacation."


@pytest.mark.django_db(transaction=True)
def test_four_uploads_at_once_never_get_the_same_number(marta):
    doc = services.create_document(marta, "Race", text_file("v1"))
    barrier, errors = threading.Barrier(4), []

    def upload(n):
        try:
            barrier.wait()
            services.upload_version(marta, doc, text_file(f"content {n}"), f"upload {n}")
        except Exception as error:  # noqa: BLE001 - the test reports whatever happens
            errors.append(repr(error))
        finally:
            connections.close_all()

    threads = [threading.Thread(target=upload, args=(n,)) for n in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert errors == []
    assert sorted(doc.versions.exclude(number=1).values_list("number", flat=True)) == [2, 3, 4, 5]


def test_a_reader_cannot_upload(doc, luca, grant):
    grant(doc, luca, Access.Level.READ)
    with pytest.raises(PermissionDenied):
        services.upload_version(luca, doc, text_file("something else"))


def test_an_editor_can_upload(doc, luca, grant):
    grant(doc, luca, Access.Level.EDIT)
    version = services.upload_version(luca, doc, text_file("an editor's text"))
    assert version.author == luca


def test_nothing_can_be_uploaded_during_a_review(doc, marta, luca):
    services.send_for_review(marta, doc, [luca], SEQ)
    with pytest.raises(services.DomainError, match="under review"):
        services.upload_version(marta, doc, text_file("a new text"))


def test_an_identical_file_does_not_create_a_version(doc, marta):
    with pytest.raises(services.DomainError, match="identical"):
        services.upload_version(marta, doc, text_file("Twenty-six days of paid vacation.", "other-name.txt"))
    assert doc.versions.count() == 1


def test_a_new_version_takes_an_approved_document_back_to_draft(doc, marta, luca):
    services.send_for_review(marta, doc, [luca], FREE)
    services.decide(luca, doc, True)
    doc.refresh_from_db()
    assert doc.state == Document.State.APPROVED
    services.upload_version(marta, doc, text_file("a corrected text"))
    doc.refresh_from_db()
    assert doc.state == Document.State.DRAFT


def test_a_binary_file_is_refused_with_a_clear_message(marta, settings):
    with pytest.raises(services.DomainError, match="UTF-8"):
        services.create_document(marta, "Binary", text_file(b"\xff\xfe\x00\x01", "photo.png"))
    assert Document.objects.count() == 0
    assert stored_files(settings) == []


def test_a_file_that_is_too_large_is_refused(marta, settings):
    settings.MAX_FILE_SIZE = 100
    with pytest.raises(services.DomainError, match="too large"):
        services.create_document(marta, "Big", text_file("x" * 101))


def test_a_failure_after_writing_the_file_leaves_no_orphan(marta, settings, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("failure after the file was written")

    monkeypatch.setattr(services, "_event", boom)
    with pytest.raises(RuntimeError):
        services.create_document(marta, "Doomed", text_file("some text"))
    assert Document.objects.count() == 0
    assert stored_files(settings) == []


def test_every_action_leaves_a_trace_in_the_log(doc, marta):
    services.upload_version(marta, doc, text_file("again, with changes"), "second")
    assert [e.kind for e in doc.events.all()] == ["created", "new_version"]
