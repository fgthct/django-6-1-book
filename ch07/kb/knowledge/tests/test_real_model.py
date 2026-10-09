import os

import pytest
from django.core.management import call_command

from knowledge import embedder
from knowledge.evaluation import QUESTIONS, evaluate
from knowledge.search import hybrid_search
from knowledge.tests.conftest import CORPUS_DIR

pytestmark = pytest.mark.skipif(not os.environ.get("KB_REAL_MODEL"), reason="uses the real model: set KB_REAL_MODEL=1")


@pytest.fixture(autouse=True)
def fake_model(monkeypatch):
    """Overrides the autouse fixture of conftest: here we want the real model."""
    embedder._model.cache_clear()


def test_hybrid_search_with_the_real_model_stays_good(db):
    call_command("import_docs", str(CORPUS_DIR), verbosity=0)
    score = evaluate(lambda t: [r.chunk for r in hybrid_search(t, 10)], QUESTIONS)
    assert score.hit_3 >= 0.9 and score.mrr >= 0.85
