"""The HNSW index skips the NULLs, the sequential scan doesn't: the result depends on the plan."""
import django
from django.db import connection, transaction

django.setup()

from pgvector.django import CosineDistance  # noqa: E402

from knowledge.embedder import embed  # noqa: E402
from knowledge.models import Chunk  # noqa: E402


class Rollback(Exception):
    pass


def count(settings_sql, exclude_null):
    with connection.cursor() as c:
        c.execute("RESET enable_seqscan; RESET enable_indexscan; RESET enable_bitmapscan")
        c.execute(settings_sql)
    qs = Chunk.objects.annotate(distance=CosineDistance("embedding", vector))
    if exclude_null:
        qs = qs.exclude(embedding=None)
    return len(list(qs.order_by("distance", "pk")[:50]))


vector = embed(["vacation"])[0]
try:
    with transaction.atomic():
        ids = list(Chunk.objects.values_list("pk", flat=True)[:6])
        Chunk.objects.filter(pk__in=ids).update(embedding=None)
        total, without = Chunk.objects.count(), Chunk.objects.filter(embedding=None).count()
        print(f"total chunks: {total} - without a vector: {without}")
        seq = "SET LOCAL enable_indexscan = off; SET LOCAL enable_bitmapscan = off"
        idx = "SET LOCAL enable_seqscan = off"
        print(f"sequential scan : {count(seq, False)} results")
        print(f"HNSW index      : {count(idx, False)} results")
        print(f"with exclude(NULL): always {count(seq, True)}/{count(idx, True)}")
        raise Rollback
except Rollback:
    pass
