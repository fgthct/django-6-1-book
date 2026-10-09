import pytest
from django.db import OperationalError
from django.db.migrations.executor import MigrationExecutor


def test_liveness_works_without_the_database(client, monkeypatch):
    # No `django_db` marker, and in addition any attempt to connect fails the test:
    # the marker alone does not catch a connection that is already open.
    from django.db import connection

    def forbidden():
        raise AssertionError("the liveness check touched the database")

    monkeypatch.setattr(connection, "ensure_connection", forbidden)
    response = client.get("/health/")
    assert response.status_code == 200 and response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_readiness_answers_200_in_normal_conditions(client):
    response = client.get("/ready/")
    assert response.status_code == 200 and response.json() == {"status": "ready"}


@pytest.mark.django_db
def test_readiness_answers_503_with_a_migration_missing(client, monkeypatch):
    monkeypatch.setattr(MigrationExecutor, "migration_plan", lambda self, targets: [("documents.0005", False)])
    response = client.get("/ready/")
    assert response.status_code == 503
    assert response.json() == {"status": "migrations to apply", "how_many": 1}


@pytest.mark.django_db
def test_readiness_answers_503_with_the_database_unreachable(client, monkeypatch):
    from django.db import connection

    def broken():
        raise OperationalError("the database is gone")

    monkeypatch.setattr(connection, "ensure_connection", broken)
    response = client.get("/ready/")
    assert response.status_code == 503 and response.json() == {"status": "database unreachable"}


def test_the_two_checks_accept_only_get(client):
    for url in ("/health/", "/ready/"):
        assert client.post(url).status_code == 405
