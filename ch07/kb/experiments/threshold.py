"""Distance of the best chunk: on-topic questions against off-topic ones."""
import django

django.setup()

from knowledge.evaluation import OFF_TOPIC, QUESTIONS  # noqa: E402
from knowledge.search import search_by_meaning  # noqa: E402


def best(text):
    return search_by_meaning(text, 1)[0].distance


on = sorted(best(q.text) for q in QUESTIONS if q.kind == "paraphrase")
off = sorted(best(t) for t in OFF_TOPIC)
print("on topic :", " ".join(f"{d:.2f}" for d in on))
print("off topic:", " ".join(f"{d:.2f}" for d in off))
