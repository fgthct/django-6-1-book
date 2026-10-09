import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from documents import services
from documents.models import Access, Review


@pytest.fixture(autouse=True)
def test_environment(settings, tmp_path):
    """The fake embedder (no downloads), a temporary folder for the files, and a fast password hasher."""
    settings.EMBEDDING_BACKEND = "fake"
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


def make_user(username, first, last):
    return get_user_model().objects.create_user(
        username=username, first_name=first, last_name=last, email=f"{username}@example.test", password="pw"
    )


@pytest.fixture
def marta(db):
    return make_user("marta", "Marta", "Bianchi")


@pytest.fixture
def luca(db):
    return make_user("luca", "Luca", "Neri")


@pytest.fixture
def giulia(db):
    return make_user("giulia", "Giulia", "Verdi")


@pytest.fixture
def paolo(db):
    return make_user("paolo", "Paolo", "Gialli")


def text_file(content, name="notes.txt"):
    data = content.encode() if isinstance(content, str) else content
    return SimpleUploadedFile(name, data, content_type="text/plain")


SEQ = Review.Mode.SEQUENTIAL
FREE = Review.Mode.FREE


@pytest.fixture
def doc(marta):
    """A draft owned by Marta, with one version."""
    return services.create_document(marta, "Vacation policy", text_file("Twenty-six days of paid vacation."))


@pytest.fixture
def grant():
    def _grant(document, user, level=Access.Level.READ):
        return Access.objects.create(document=document, user=user, level=level)

    return _grant
