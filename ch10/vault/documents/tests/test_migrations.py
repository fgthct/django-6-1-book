import hashlib

import pytest
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

LAST = ("documents", "0004_remove_text_from_document")


def migrate(target):
    executor = MigrationExecutor(connection)
    executor.migrate([target])
    return MigrationExecutor(connection).loader.project_state([target]).apps


@pytest.fixture
def back_to_the_latest(transactional_db):
    yield
    migrate(LAST)  # whatever the test did, the database ends up at the latest migration


@pytest.mark.django_db(transaction=True)
def test_the_data_migration_brings_the_prototype_into_the_model_with_versions(back_to_the_latest):
    old = migrate(("documents", "0001_initial"))
    User = old.get_model("auth", "User")
    Document = old.get_model("documents", "Document")
    marta = User.objects.create(username="marta", email="m@example.test")
    Document.objects.create(title="Vacation policy", text="Twenty-six days.", owner=marta)
    Document.objects.create(title="No text", text="", owner=marta)

    new = migrate(LAST)
    Document, Version = new.get_model("documents", "Document"), new.get_model("documents", "Version")
    assert Document.objects.count() == 2 and Version.objects.count() == 2
    d = Document.objects.get(title="Vacation policy")
    v = d.current_version
    assert (v.number, v.text, v.note, v.file_name) == (1, "Twenty-six days.", "Imported from the prototype", "vacation-policy.txt")
    assert v.hash == hashlib.sha256(b"Twenty-six days.").hexdigest()
    assert v.author_id == d.owner_id and not v.file and d.state == "draft"


@pytest.mark.django_db(transaction=True)
def test_the_way_back_returns_the_text_and_going_forward_again_creates_no_duplicates(back_to_the_latest):
    old = migrate(("documents", "0001_initial"))
    User, Document = old.get_model("auth", "User"), old.get_model("documents", "Document")
    marta = User.objects.create(username="marta", email="m@example.test")
    Document.objects.create(title="Vacation policy", text="Twenty-six days.", owner=marta)

    migrate(LAST)
    back = migrate(("documents", "0002_versions_reviews_chunks"))  # undoes 0004 and 0003
    assert back.get_model("documents", "Document").objects.get().text == "Twenty-six days."

    forward = migrate(LAST)
    assert forward.get_model("documents", "Version").objects.count() == 1


@pytest.mark.django_db
def test_the_models_and_the_database_agree():
    call_command("makemigrations", "--check", "--dry-run")
