import re
import zlib
from pathlib import Path

import numpy as np
import pytest
from django.conf import settings
from django.core.management import call_command

from knowledge import embedder

CORPUS_DIR = Path(__file__).resolve().parent.parent / "corpus"


class FakeModel:
    """A deterministic "model": every word lights up one dimension.

    It doesn't understand synonyms, but it is instant, reproducible and respects
    the fastembed contract (`embed` produces numpy arrays). It is enough to test
    *our* code: chunking, import, SQL, fusion.
    """

    def embed(self, texts):
        for text in texts:
            v = np.zeros(settings.EMBEDDING_DIMENSIONS, dtype=np.float32)
            for word in re.findall(r"\w+", text.lower()):
                v[zlib.crc32(word.encode()) % settings.EMBEDDING_DIMENSIONS] += 1.0
            yield v


@pytest.fixture(autouse=True)
def fake_model(monkeypatch):
    # We replace _model, NOT embed: that way the check on the dimensions stays the real one.
    monkeypatch.setattr(embedder, "_model", lambda: FakeModel())


@pytest.fixture
def corpus(db):
    """The six documents, imported with the fake model."""
    call_command("import_docs", str(CORPUS_DIR), verbosity=0)


@pytest.fixture
def docs_folder(tmp_path):
    """A temporary folder with two small documents."""
    (tmp_path / "a.md").write_text("# Alpha\n\n## One\n\nFirst paragraph about apples.\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Beta\n\n## Two\n\nSecond paragraph about bananas.\n", encoding="utf-8")
    return tmp_path
