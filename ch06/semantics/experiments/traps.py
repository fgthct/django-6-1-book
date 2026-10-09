"""Two typical mistakes: the noisy one and the silent one."""
import django
import numpy as np
from django.db import DataError, transaction

django.setup()

from sentences.embedder import embed  # noqa: E402
from sentences.models import Sentence  # noqa: E402
from sentences.search import search_by_meaning  # noqa: E402

print("1) a 384-dimension vector against a 768-dimension column:")
try:
    with transaction.atomic():
        list(search_by_meaning("x", vector=[0.1] * 384))
except Exception as e:  # noqa: BLE001
    print("    " + str(e).splitlines()[0])

print("\n2) a random 768-dimension vector (no error, no warning):")
rng = np.random.default_rng(7)
for s in search_by_meaning("x", limit=3, vector=rng.normal(size=768).tolist()):
    print(f"    {s.distance:.3f}  [{s.topic}] {s.text[:60]}")
print(f"    ({Sentence.objects.count()} sentences in the corpus: the results look like answers, but they are not)")
