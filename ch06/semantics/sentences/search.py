from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from pgvector.django import CosineDistance

from .embedder import embed
from .models import Sentence


def search_by_meaning(question: str, limit: int = 5, vector=None):
    """The sentences closest to the question, by cosine distance (0 = identical)."""
    if vector is None:
        vector = embed([question])[0]
    return (
        Sentence.objects.exclude(embedding=None)
        .annotate(distance=CosineDistance("embedding", vector))
        .order_by("distance", "pk")[:limit]
    )


def search_by_words(question: str, limit: int = 5):
    """The full-text search of Chapter 3, on the same corpus, for comparison."""
    query = SearchQuery(question, config="english", search_type="websearch")
    vector = SearchVector("text", config="english")
    return (
        Sentence.objects.annotate(search=vector)
        .filter(search=query)  # only the sentences that *contain* the terms
        .annotate(rank=SearchRank(vector, query))
        .order_by("-rank", "pk")[:limit]
    )
