from dataclasses import dataclass

from django.conf import settings

from .search import search

NOT_FOUND = "I found nothing in the documents you can see that answers this question."


@dataclass
class Answer:
    text: str
    sources: list


def answer(user, question):
    """An extractive answer: the best passages with their sources, but only if the best one is close enough."""
    results = search(user, question, limit=3)
    if not results or results[0].distance > settings.RAG_MAX_DISTANCE:
        return Answer(NOT_FOUND, [])
    return Answer(results[0].text, results)
