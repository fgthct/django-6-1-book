from django.db import connection, transaction
from django.db.models import F
from pgvector.django import CosineDistance

from .embedder import embed
from .models import Chunk, Document


def search(user, question, limit=5, vector=None):
    """The passages closest to the question, among the documents `user` can see and nobody else's."""
    if vector is None:
        vector = embed([question])[0]
    visible = Document.objects.visible_to(user)
    with transaction.atomic():
        with connection.cursor() as cursor:
            # Without this line the HNSW index looks for its ~40 candidates *before* applying the
            # permissions filter, and can return fewer results than it should, down to zero (see the chapter).
            cursor.execute("SET LOCAL hnsw.iterative_scan = 'relaxed_order'")
        results = list(
            Chunk.objects.filter(
                version__document__in=visible,
                version__document__current_version=F("version"),
            )
            .exclude(embedding=None)
            .select_related("version__document")
            .annotate(distance=CosineDistance("embedding", vector))
            .order_by("distance", "pk")[:limit]
        )
    # With relaxed_order the results can arrive "almost" in order: we put them back in order ourselves.
    results.sort(key=lambda c: (c.distance, c.pk))
    return results
