import sys
import types

import pytest
from django.core.exceptions import ImproperlyConfigured

from documents import embedder


class FakeArray(list):
    def tolist(self):
        return list(self)


def install_fake_fastembed(monkeypatch, dimensions):
    class TextEmbedding:
        def __init__(self, model, cache_dir=None):
            self.model, self.cache_dir = model, cache_dir

        def embed(self, texts):
            return [FakeArray([0.5] * dimensions) for _ in texts]

    embedder._model.cache_clear()
    monkeypatch.setitem(sys.modules, "fastembed", types.SimpleNamespace(TextEmbedding=TextEmbedding))
    yield
    embedder._model.cache_clear()


@pytest.fixture
def real_backend(settings):
    settings.EMBEDDING_BACKEND = "fastembed"
    settings.EMBEDDING_DIMENSIONS = 8


def test_the_real_backend_calls_the_model_and_returns_plain_lists(monkeypatch, real_backend):
    for _ in install_fake_fastembed(monkeypatch, 8):
        vectors = embedder.embed(["one", "two"])
        assert vectors == [[0.5] * 8, [0.5] * 8]
        assert type(vectors[0]) is list


def test_a_model_with_the_wrong_dimensions_fails_with_a_clear_message(monkeypatch, real_backend):
    for _ in install_fake_fastembed(monkeypatch, 384):
        with pytest.raises(ImproperlyConfigured, match="384 dimensions, but EMBEDDING_DIMENSIONS is 8"):
            embedder.embed(["one"])


def test_the_fake_backend_does_not_touch_fastembed(monkeypatch):
    monkeypatch.setitem(sys.modules, "fastembed", None)  # importing it would fail
    assert len(embedder.embed(["hello"])[0]) == 768
