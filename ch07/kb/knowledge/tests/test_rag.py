import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from knowledge import rag
from knowledge.rag import NOT_KNOWN, answer, generate_ollama


def test_a_question_on_topic_gets_the_best_passage_and_its_sources(corpus, settings):
    settings.RAG_MAX_DISTANCE = 2.0  # the fake model doesn't understand: we only test the flow
    a = answer("How many vacation days do I get? 26 days of vacation")
    assert a.found and "26 days" in a.text
    assert len(a.sources) == settings.RAG_CHUNKS_IN_CONTEXT


def test_far_questions_get_dont_know_without_calling_the_generator(corpus, settings, monkeypatch):
    settings.RAG_MAX_DISTANCE = 0.0
    monkeypatch.setitem(rag.GENERATORS, "extractive", lambda *a: pytest.fail("must not be called"))
    a = answer("What is the capital of Australia?")
    assert a.text == NOT_KNOWN and a.sources == [] and not a.found


def test_with_an_empty_database_the_answer_is_dont_know(db):
    assert answer("anything").found is False


def test_the_threshold_decides(corpus, settings):
    settings.RAG_MAX_DISTANCE = 0.0
    assert not answer("vacation days").found
    settings.RAG_MAX_DISTANCE = 2.0
    assert answer("vacation days").found


def test_the_number_of_chunks_comes_from_the_settings(corpus, settings):
    settings.RAG_MAX_DISTANCE = 2.0
    settings.RAG_CHUNKS_IN_CONTEXT = 2
    assert len(answer("vacation days").sources) == 2


def test_the_generator_is_chosen_by_the_settings(corpus, settings, monkeypatch):
    settings.RAG_MAX_DISTANCE = 2.0
    settings.RAG_GENERATOR = "ollama"
    monkeypatch.setitem(rag.GENERATORS, "ollama", lambda prompt, passages: "from the model")
    assert answer("vacation days").text == "from the model"


def test_the_prompt_passed_to_the_generator_contains_the_passages(corpus, settings, monkeypatch):
    settings.RAG_MAX_DISTANCE = 2.0
    seen = {}
    monkeypatch.setitem(rag.GENERATORS, "extractive", lambda prompt, passages: seen.update(p=prompt) or "x")
    answer("vacation days")
    assert "<<<PASSAGE" in seen["p"] and "Question: vacation days" in seen["p"]


class FakeOllama(BaseHTTPRequestHandler):
    received = {}

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOllama.received = {"path": self.path, "body": body}
        payload = json.dumps({"response": "  The answer.  "}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


def test_the_ollama_generator_speaks_the_protocol_we_expect(settings):
    server = HTTPServer(("127.0.0.1", 0), FakeOllama)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    settings.OLLAMA_URL = f"http://127.0.0.1:{server.server_port}"
    settings.OLLAMA_MODEL = "some-model"
    try:
        text = generate_ollama("the prompt", ["p"])
    finally:
        server.shutdown()
    assert text == "The answer."
    assert FakeOllama.received["path"] == "/api/generate"
    assert FakeOllama.received["body"] == {"model": "some-model", "prompt": "the prompt", "stream": False}


def test_the_ollama_generator_is_really_reached_through_answer(corpus, settings):
    server = HTTPServer(("127.0.0.1", 0), FakeOllama)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    settings.OLLAMA_URL = f"http://127.0.0.1:{server.server_port}"
    settings.RAG_GENERATOR = "ollama"
    settings.RAG_MAX_DISTANCE = 2.0
    try:
        a = answer("vacation days")
    finally:
        server.shutdown()
    assert a.text == "The answer." and FakeOllama.received["path"] == "/api/generate"
    assert "<<<PASSAGE" in FakeOllama.received["body"]["prompt"]
