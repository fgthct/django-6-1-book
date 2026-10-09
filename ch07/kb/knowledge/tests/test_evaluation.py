from pathlib import Path

from knowledge.evaluation import OFF_TOPIC, QUESTIONS, Question, answer_position, evaluate
from knowledge.tests.conftest import CORPUS_DIR


class Fake:
    def __init__(self, text):
        self.text = text


def test_every_expected_answer_really_exists_in_the_documents():
    """If the gold set lies, all the metrics lie with it."""
    corpus = " ".join(p.read_text(encoding="utf-8") for p in Path(CORPUS_DIR).glob("*.md")).lower()
    missing = [q.expected for q in QUESTIONS if q.expected.lower() not in corpus]
    assert missing == []


def test_the_set_has_eighteen_questions_in_two_families():
    assert len(QUESTIONS) == 18
    assert sum(q.kind == "paraphrase" for q in QUESTIONS) == 12
    assert sum(q.kind == "exact" for q in QUESTIONS) == 6


def test_there_are_six_off_topic_questions():
    assert len(OFF_TOPIC) == 6


def test_answer_position_is_one_based():
    q = Question("q", "needle", "exact")
    assert answer_position(q, [Fake("hay"), Fake("a needle here")]) == 2
    assert answer_position(q, [Fake("hay")]) is None


def test_the_metrics_of_a_perfect_strategy():
    qs = [Question("a", "A", "exact"), Question("b", "B", "exact")]
    score = evaluate(lambda t: [Fake(t.upper())], qs)
    assert (score.hit_1, score.hit_3, score.mrr) == (1.0, 1.0, 1.0)


def test_the_metrics_of_a_strategy_that_is_second_or_missing():
    qs = [Question("a", "A", "exact"), Question("b", "B", "exact")]
    score = evaluate(lambda t: [Fake("zzz"), Fake(t.upper())] if t == "a" else [Fake("zzz")], qs)
    assert score.hit_1 == 0.0 and score.hit_3 == 0.5 and score.mrr == 0.25
