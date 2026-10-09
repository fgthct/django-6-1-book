from functools import lru_cache

from django.conf import settings


@lru_cache(maxsize=1)
def _model():
    # The import is down here on purpose: loading fastembed and the model takes seconds,
    # and tests, migrations and commands that don't search should not pay for it.
    from fastembed import TextEmbedding

    return TextEmbedding(settings.EMBEDDING_MODEL, cache_dir=settings.EMBEDDING_CACHE)


def embed(texts: list[str]) -> list[list[float]]:
    """Turn a list of texts into a list of vectors (lists of floats)."""
    vectors = [v.tolist() for v in _model().embed(texts)]
    for v in vectors:
        if len(v) != settings.EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"The model returns {len(v)} dimensions, "
                f"but the project expects {settings.EMBEDDING_DIMENSIONS}."
            )
    return vectors
