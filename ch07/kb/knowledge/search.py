import re
from dataclasses import dataclass

from django.contrib.postgres.search import SearchQuery, SearchRank
from pgvector.django import CosineDistance

from .embedder import embed
from .models import Chunk


def search_by_meaning(question: str, limit: int = 20, vector=None):
    if vector is None:
        vector = embed([question])[0]
    return (
        Chunk.objects.exclude(embedding=None)
        .select_related("document")
        .annotate(distance=CosineDistance("embedding", vector))
        .order_by("distance", "pk")[:limit]
    )


def search_by_words(question: str, limit: int = 20, all_words: bool = False):
    """Full-text search on the text of the chunks.

    With `websearch` PostgreSQL puts all the words in AND: a question in
    natural language ("How many vacation days do I get in a year?") never
    finds anything, because no passage contains all of them. For a question
    it is enough that a passage contains *some* of them: we join them with `or`
    and let ts_rank put the ones with the most words on top.
    """
    if all_words:
        text = question
    else:
        text = " or ".join(re.findall(r"[\w@.\-:]+", question))
    query = SearchQuery(text, config="english", search_type="websearch")
    return (
        Chunk.objects.filter(search=query)
        .select_related("document")
        .annotate(rank=SearchRank("search", query))
        .order_by("-rank", "pk")[:limit]
    )


def rrf_fusion(rankings: list[list], k: int = 60) -> list[tuple]:
    """Reciprocal Rank Fusion: each item gets 1/(k + position) from every ranking.

    It doesn't look at scores, only at positions: that is why it works even if
    one ranking speaks of cosine distances and the other of ts_rank, which are
    not comparable. Returns [(item, score)] from the best.
    """
    scores: dict = {}
    for ranking in rankings:
        for position, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + position)
    # With equal scores the item that appeared first wins: the order is stable.
    return sorted(scores.items(), key=lambda pair: -pair[1])


@dataclass
class Result:
    chunk: Chunk
    score: float
    meaning_position: int | None
    words_position: int | None


def hybrid_search(
    question: str, limit: int = 5, candidates: int = 20, vector=None, all_words: bool = True
) -> list[Result]:
    semantic = list(search_by_meaning(question, candidates, vector))
    textual = list(search_by_words(question, candidates, all_words))
    pos_s = {c.pk: i for i, c in enumerate(semantic, start=1)}
    pos_t = {c.pk: i for i, c in enumerate(textual, start=1)}
    by_id = {c.pk: c for c in [*semantic, *textual]}
    fused = rrf_fusion([[c.pk for c in semantic], [c.pk for c in textual]])
    return [
        Result(by_id[pk], score, pos_s.get(pk), pos_t.get(pk))
        for pk, score in fused[:limit]
    ]
