import sys

import django

django.setup()

from knowledge.search import hybrid_search  # noqa: E402

question = sys.argv[1]
ALL = len(sys.argv) > 2 and sys.argv[2] == "and"
print("Question:", question)
print()
print("    RRF  meaning  words  chunk")
for r in hybrid_search(question, 5, all_words=ALL):
    where = f"{r.chunk.document.title} · {r.chunk.section}"
    print(f"{r.score:>7.4f} {str(r.meaning_position or '-'):>8} {str(r.words_position or '-'):>6}  {where}")
