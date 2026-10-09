import json
import urllib.request
from dataclasses import dataclass, field

from django.conf import settings

from .embedder import embed
from .prompts import rag_prompt
from .search import Result, hybrid_search, search_by_meaning

NOT_KNOWN = "I don't know: I found nothing in the documents that answers this question."


@dataclass
class Answer:
    text: str
    sources: list[Result] = field(default_factory=list)
    found: bool = True


def generate_extractive(prompt: str, passages: list[str]) -> str:
    """No model: the best passage, as it is. It cannot make anything up."""
    return passages[0]


def generate_ollama(prompt: str, passages: list[str]) -> str:
    request = urllib.request.Request(
        f"{settings.OLLAMA_URL}/api/generate",
        data=json.dumps(
            {"model": settings.OLLAMA_MODEL, "prompt": prompt, "stream": False}
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)["response"].strip()


GENERATORS = {"extractive": generate_extractive, "ollama": generate_ollama}


def answer(question: str) -> Answer:
    # We compute the question's vector once and reuse it.
    vector = embed([question])[0]
    best = list(search_by_meaning(question, 1, vector))
    if not best or best[0].distance > settings.RAG_MAX_DISTANCE:
        return Answer(NOT_KNOWN, [], found=False)

    sources = hybrid_search(question, settings.RAG_CHUNKS_IN_CONTEXT, vector=vector)
    passages = [r.chunk.text for r in sources]
    prompt = rag_prompt(question, passages)
    text = GENERATORS[settings.RAG_GENERATOR](prompt, passages)
    return Answer(text, sources)
