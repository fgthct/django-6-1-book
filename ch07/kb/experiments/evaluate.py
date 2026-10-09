"""Compare the search strategies on the set of questions."""
import django

django.setup()

from knowledge.evaluation import QUESTIONS, answer_position, evaluate  # noqa: E402
from knowledge.search import hybrid_search, search_by_meaning, search_by_words  # noqa: E402

STRATEGIES = {
    "words": lambda t: search_by_words(t, 10),
    "words (AND)": lambda t: search_by_words(t, 10, all_words=True),
    "meaning": lambda t: search_by_meaning(t, 10),
    "hybrid (AND)": lambda t: [r.chunk for r in hybrid_search(t, 10, all_words=True)],
    "hybrid (OR)": lambda t: [r.chunk for r in hybrid_search(t, 10, all_words=False)],
}

for label, kind in [("paraphrase", "paraphrase"), ("exact", "exact"), ("all", None)]:
    subset = [q for q in QUESTIONS if kind is None or q.kind == kind]
    print(f"\n== {label} ({len(subset)} questions)")
    for name, strategy in STRATEGIES.items():
        s = evaluate(strategy, subset)
        print(f"{name:<13} hit@1={s.hit_1:.2f} hit@3={s.hit_3:.2f} MRR={s.mrr:.2f}")

print("\nQuestions that even the hybrid search doesn't put first:")
for name in ("meaning", "hybrid (AND)"):
    for q in QUESTIONS:
        pos = answer_position(q, list(STRATEGIES[name](q.text)))
        if pos != 1:
            print(f"{name:<13} pos={pos}  {q.text}")
