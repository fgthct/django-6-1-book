from django.shortcuts import render

from . import rag, search as retrieval

MODES = {
    "hybrid": "Hybrid (meaning + words)",
    "meaning": "Meaning only",
    "words": "Words only",
}


def index(request):
    return render(request, "knowledge/index.html", {"modes": MODES, "question": "", "mode": "hybrid", "results": []})


def search(request):
    question = request.GET.get("q", "").strip()
    mode = request.GET.get("mode", "hybrid")
    if mode not in MODES:
        mode = "hybrid"
    results = []
    if question:
        if mode == "hybrid":
            results = retrieval.hybrid_search(question, 5)
        elif mode == "meaning":
            results = [
                retrieval.Result(c, 1 - c.distance, i, None)
                for i, c in enumerate(retrieval.search_by_meaning(question, 5), start=1)
            ]
        else:
            results = [
                retrieval.Result(c, c.rank, None, i)
                for i, c in enumerate(retrieval.search_by_words(question, 5), start=1)
            ]
    context = {"question": question, "mode": mode, "results": results}
    return render(request, "knowledge/index.html#results", context)


def ask(request):
    question = request.GET.get("q", "").strip()
    answer = rag.answer(question) if question else None
    return render(request, "knowledge/index.html#answer", {"question": question, "answer": answer})
