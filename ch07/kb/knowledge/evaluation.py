"""A set of questions written in advance, with the right answer known."""
import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Question:
    text: str
    expected: str  # a phrase that the right passage MUST contain
    kind: str  # "paraphrase" or "exact"


QUESTIONS = [
    # Paraphrases: the question doesn't use the words of the document.
    Question("How many vacation days am I entitled to in a year?", "26 days of vacation", "paraphrase"),
    Question("If I feel unwell, who do I have to notify and when?", "by 9:00 AM", "paraphrase"),
    Question("Can I work from the sofa at home?", "two days a week", "paraphrase"),
    Question("How much do I get if I go on a business trip with my own car?", "0.35 euros per kilometer", "paraphrase"),
    Question("I lost a receipt that is two months old, can I still get it paid for?", "declaration of loss", "paraphrase"),
    Question("Someone stole my computer, who do I phone?", "extension 4100", "paraphrase"),
    Question("What if I can't use my phone for the login code any more?", "call the IT desk", "paraphrase"),
    Question("How much data could we lose in the worst case?", "we lose one day of data", "paraphrase"),
    Question("How soon must I answer a customer?", "within four working hours", "paraphrase"),
    Question("An angry customer wants to cancel, what do I do?", "hand the ticket to your manager", "paraphrase"),
    Question("Who looks after me when I join the company?", "buddy", "paraphrase"),
    Question("When can a customer get their money back?", "within 14 days of the purchase", "paraphrase"),
    # Exact: a code, an acronym, a number that only words can find.
    Question("form RS-12", "form RS-12", "exact"),
    Question("RPO", "(RPO)", "exact"),
    Question("02:30", "02:30", "exact"),
    Question("RTO", "(RTO)", "exact"),
    Question("VPN", "VPN", "exact"),
    Question("extension 4100", "extension 4100", "exact"),
]

OFF_TOPIC = [
    "What is the capital of Australia?",
    "How do you make carbonara?",
    "Who won the soccer championship?",
    "How much is a ticket to the moon?",
    "Explain the theory of relativity",
    "What will the weather be like tomorrow?",
]


@dataclass(frozen=True)
class Score:
    hit_1: float
    hit_3: float
    mrr: float
    milliseconds: float


def answer_position(question: Question, chunks: list) -> int | None:
    """Position (1-based) of the first chunk that contains the expected phrase."""
    for i, chunk in enumerate(chunks, start=1):
        if question.expected.lower() in chunk.text.lower():
            return i
    return None


def evaluate(strategy: Callable, questions=QUESTIONS, n: int = 3) -> Score:
    """`strategy(text)` returns the chunks in order of relevance."""
    positions, elapsed = [], 0.0
    for q in questions:
        t0 = time.perf_counter()
        chunks = list(strategy(q.text))
        elapsed += time.perf_counter() - t0
        positions.append(answer_position(q, chunks))
    total = len(questions)
    return Score(
        hit_1=sum(p == 1 for p in positions) / total,
        hit_3=sum(p is not None and p <= n for p in positions) / total,
        mrr=sum(1 / p for p in positions if p) / total,
        milliseconds=1000 * elapsed / total,
    )
