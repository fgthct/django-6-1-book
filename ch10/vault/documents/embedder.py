import math
import re
import zlib
from functools import lru_cache

from django.conf import settings


@lru_cache(maxsize=1)
def _model():
    # The import is down here on purpose: loading fastembed and the model takes seconds.
    from fastembed import TextEmbedding

    return TextEmbedding(settings.EMBEDDING_MODEL, cache_dir=settings.EMBEDDING_CACHE)


def _fake(text: str) -> list[float]:
    """A bag of words, normalized: enough to test permissions, with no meaning of its own."""
    vector = [0.0] * settings.EMBEDDING_DIMENSIONS
    for word in re.findall(r"\w+", text.lower()):
        vector[zlib.crc32(word.encode()) % settings.EMBEDDING_DIMENSIONS] += 1.0
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        vector[0], norm = 1.0, 1.0
    return [x / norm for x in vector]


def embed(texts: list[str]) -> list[list[float]]:
    """Turn a list of texts into a list of vectors."""
    if settings.EMBEDDING_BACKEND == "fake":
        return [_fake(t) for t in texts]
    return [v.tolist() for v in _model().embed(texts)]
