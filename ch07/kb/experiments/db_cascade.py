"""What does DB_CASCADE change when we delete a Document? Queries and signals."""
import django

django.setup()

from django.db import connection  # noqa: E402
from django.db.models.signals import post_delete  # noqa: E402

from knowledge.models import Chunk, Document  # noqa: E402

received = []
post_delete.connect(lambda sender, **kw: received.append(sender.__name__), weak=False)

doc = Document.objects.create(path="lab.md", title="Lab", hash="x")
for i in range(3):
    Chunk.objects.create(document=doc, position=i, text=f"chunk {i}")

queries = []
with connection.execute_wrapper(lambda ex, sql, params, many, ctx: (queries.append(sql), ex(sql, params, many, ctx))[1]):
    doc.delete()

print("Deleting a Document with 3 chunks:")
deletes = [q for q in queries if q.startswith("DELETE")]
assert len(queries) == len(deletes) == 1
print('queries run   : DELETE FROM "knowledge_document" WHERE ...   (just one)')
print(f"post_delete signals received: {sorted(set(received))}   (none for Chunk)")
print(f"chunks left   : {Chunk.objects.filter(document_id=doc.pk).count()}")
