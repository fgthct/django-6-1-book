"""Break the code on purpose, one change at a time, and run the whole suite for each."""
import shutil
import subprocess
import sys
from pathlib import Path

K = "knowledge/"
MUTANTS = [
    ("RRF: max instead of sum", K + "search.py",
     "scores.get(item, 0.0) + 1.0 / (k + position)", "max(scores.get(item, 0.0), 1.0 / (k + position))"),
    ("RRF: ascending order", K + "search.py", "key=lambda pair: -pair[1]", "key=lambda pair: pair[1]"),
    ("chunking: the piece is not reset", K + "chunking.py", "            current = []\n", ""),
    ("chunking: context lost", K + "chunking.py", 'return f"{heading}\\n{piece.text}"', "return piece.text"),
    ("model: ORM CASCADE", K + "models.py", "models.DB_CASCADE", "models.CASCADE"),
    ("model: no unique position", K + "models.py",
     "        constraints = [\n            models.UniqueConstraint(\n                fields=[\"document\", \"position\"], name=\"chunk_unique_position\"\n            )\n        ]\n",
     ""),
    ("import: ignores the model change", K + "management/commands/import_docs.py",
     "return not doc.chunks.exclude(model=settings.EMBEDDING_MODEL).exists()", "return True"),
    ("import: no transaction", K + "management/commands/import_docs.py",
     "        with transaction.atomic():\n", "        if True:\n"),
    ("import: ignores the hash", K + "management/commands/import_docs.py",
     "existing.hash == fingerprint", "True"),
    ("prompt: delimiters not removed", K + "prompts.py",
     '    clean = value.replace(DELIMITER, "").replace(CLOSING, "")\n    return f"{DELIMITER}', '    clean = value\n    return f"{DELIMITER}'),
    ("prompt: question not limited", K + "prompts.py", ".strip()[:LINE_LIMIT]", ".strip()"),
    ("prompt: interpolation without treatment allowed", K + "prompts.py",
     "            if item.format_spec not in _TREATMENTS:", "            if False:"),
    ("rag: threshold inverted", K + "rag.py", "best[0].distance > settings.RAG_MAX_DISTANCE", "best[0].distance < settings.RAG_MAX_DISTANCE"),
    ("rag: ollama generator ignored", K + "rag.py", '"ollama": generate_ollama', '"ollama": generate_extractive'),
    ("search: no filter on the words", K + "search.py", "Chunk.objects.filter(search=query)", "Chunk.objects.all()"),
    ("search: AND instead of OR", K + "search.py", '" or ".join(', '" ".join('),
    ("search: meaning doesn't exclude the nulls", K + "search.py", "Chunk.objects.exclude(embedding=None)", "Chunk.objects"),
    ("hybrid: uses only the semantic list", K + "search.py",
     "rrf_fusion([[c.pk for c in semantic], [c.pk for c in textual]])", "rrf_fusion([[c.pk for c in semantic]])"),
    ("view: mode not validated", K + "views.py", '    if mode not in MODES:\n        mode = "hybrid"\n', ""),
    ("embedder: no dimension check", K + "embedder.py", "if len(v) != settings.EMBEDDING_DIMENSIONS:", "if False:"),
    ("template: escaping disabled", K + "templates/knowledge/index.html",
     "{{ r.chunk.text|truncatewords:45 }}", "{{ r.chunk.text|truncatewords:45|safe }}"),
]

# The tests we added after the first draft (used with --first-draft).
LATE_TESTS = {
    "model: ORM CASCADE": ["test_models_and_migrations_are_aligned"],
    "model: no unique position": ["test_models_and_migrations_are_aligned"],
    "import: no transaction": ["test_a_failure_during_the_insert_leaves_the_old_content_intact"],
    "search: meaning doesn't exclude the nulls": ["test_chunks_without_an_embedding_never_appear_with_any_plan"],
    "hybrid: uses only the semantic list": ["test_hybrid_search_actually_uses_the_two_lists"],
    "view: mode not validated": ["test_an_invalid_mode_falls_back_to_hybrid"],
}

first_draft = "--first-draft" in sys.argv
survivors = 0
for name, path, old, new in MUTANTS:
    if first_draft and name not in LATE_TESTS:
        continue
    f = Path(path)
    original = f.read_text()
    assert old in original, f"pattern not found for: {name}"
    shutil.copy(f, "/tmp/mutant_backup")
    f.write_text(original.replace(old, new, 1))
    cmd = ["uv", "run", "pytest", "-q", "-x", "-p", "no:cacheprovider"]
    if first_draft:
        for t in LATE_TESTS[name]:
            cmd += ["-k", f"not {t}"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
    finally:
        shutil.copy("/tmp/mutant_backup", f)
    caught = r.returncode != 0
    survivors += not caught
    first = next((l for l in r.stdout.splitlines() if l.startswith("FAILED") or l.startswith("ERROR")), "")
    print(f"{'OK  ' if caught else 'LIVE'} {name}" + (f"   <- {first.split('::')[-1][:70]}" if caught and "-v" in sys.argv else ""))
print(f"surviving mutants: {survivors}")
