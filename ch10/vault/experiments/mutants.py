"""Break the code on purpose, one change at a time, and run every test after each change.

    python experiments/mutants.py            # the complete suite
    python experiments/mutants.py --check    # only verify that every pattern is found
"""
import atexit
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PERM = "documents/permissions.py"
M = "documents/models.py"
V = "documents/views.py"
S = "documents/services.py"
T = "documents/tasks.py"
SE = "documents/search.py"
RAG = "documents/rag.py"
MIG2 = "documents/migrations/0002_versions_reviews_chunks.py"
MIG3 = "documents/migrations/0003_text_into_first_version.py"
CSS = "static/app.css"
BASE = "documents/templates/documents/base.html"
DETAIL = "documents/templates/documents/detail.html"
CFG = "config/settings.py"

MUTANTS = [
    ("permissions: the accesses don't count", PERM, "return level or NONE", "return NONE"),
    ("permissions: the owner doesn't see their own", M, "Q(owner=user)\n            | Exists(", "Q(pk__in=[])\n            | Exists("),
    ("permissions: everybody sees everything", M, "Q(owner=user)\n            | Exists(", "Q(pk__isnull=False)\n            | Exists("),
    ("permissions: the owner only counts as “edit”", PERM, "        return OWNER\n", "        return EDIT\n"),
    ("permissions: exact level instead of minimum", PERM, "if level_of(user, document) < minimum:", "if level_of(user, document) != minimum:"),
    ("view: document looked up among all", V, "visible = Document.objects.visible_to(request.user).select_related(", "visible = Document.objects.all().select_related("),
    ("files: orphans are not cleaned up", S, "        for name in saved:\n            default_storage.delete(name)", "        for name in saved:\n            pass"),
    ("versions: no lock on the document", S, "        # The lock on the document's row: two uploads at once don't get the same number.\n        document = Document.objects.select_for_update().get(pk=document.pk)", "        document = Document.objects.get(pk=document.pk)"),
    ("versions: edit permission not checked", S, "        permissions.require(user, document, permissions.EDIT)\n", "        pass\n"),
    ("versions: uploads allowed during the review", S, "if document.state == Document.State.IN_REVIEW:", "if False:"),
    ("versions: an identical file is accepted", S, "if current is not None and _read(file)[2] == current.hash:", "if False:"),
    ("versions: the approved stays approved", S, "            document.state = Document.State.DRAFT  # a new version has to be approved again\n", "            pass\n"),
    ("review: whoever can only edit chooses the reviewers", S, '    """Only the owner chooses the reviewers, and only the owner."""\n    document = Document.objects.select_for_update().get(pk=document.pk)\n    permissions.require(user, document, permissions.OWNER)', '    """Only the owner chooses the reviewers, and only the owner."""\n    document = Document.objects.select_for_update().get(pk=document.pk)\n    permissions.require(user, document, permissions.EDIT)'),
    ("review: the owner can be a reviewer", S, "if document.owner_id in ids:", "if False:"),
    ("review: duplicate reviewers accepted", S, "if len(set(ids)) != len(ids):", "if False:"),
    ("review: no limit on the reviewers", S, "if len(ids) > MAX_REVIEWERS:", "if False:"),
    ("review: the reviewers don't get access", S, "        Access.objects.get_or_create(document=document, user=reviewer)  # whoever has to read, can read\n", "        pass\n"),
    ("review: in sequence everybody is notified at once", S, "to_notify = reviewers[:1] if mode == Review.Mode.SEQUENTIAL else reviewers", "to_notify = reviewers"),
    ("review: in free mode only the first is notified", S, "to_notify = reviewers[:1] if mode == Review.Mode.SEQUENTIAL else reviewers", "to_notify = reviewers[:1]"),
    ("review: the message doesn't reach the reviewers", S, 'f"{user} asks you to review “{document.title}” (version {document.current_version.number}).\\n\\n{message}")', 'f"{user} asks you to review “{document.title}” (version {document.current_version.number}).")'),
    ("decision: no lock", S, "    # The same lock as \"send\" and \"upload\": two reviewers pressing together are put in line.\n    document = Document.objects.select_for_update().get(pk=document.pk)", "    document = Document.objects.get(pk=document.pk)"),
    ("decision: the order of the turns is ignored", S, "if next_up.pk != mine.pk:", "if False:"),
    ("decision: sending back without a comment", S, "if not approve and not comment.strip():", "if False:"),
    ("decision: in free mode everybody has to approve", S, "if review.mode == Review.Mode.FREE or not still.exists():", "if not still.exists():"),
    ("decision: sending back doesn't return to draft", S, '        document.state = Document.State.DRAFT\n        document.save(update_fields=["state"])\n        _event(user, document, "sent_back", comment)', '        _event(user, document, "sent_back", comment)'),
    ("decision: you can decide twice", S, "if mine.decision != Participant.Decision.PENDING:", "if False:"),
    ("decision: whoever is not a reviewer can decide too", S, "    if mine is None:\n        raise PermissionDenied", "    if False:\n        raise PermissionDenied"),
    ("decision: the other reviewers don't become “superseded”", S, "review.participants.filter(decision=Participant.Decision.PENDING).update(", "review.participants.filter(decision=Participant.Decision.PENDING).none().update("),
    ("accesses: a reviewer's access can be revoked", S, "    if taking_part:", "    if False:"),
    ("review: anybody cancels", S, "        permissions.require(user, document, permissions.OWNER)\n        review = document.reviews.filter(status=Review.Status.OPEN).first()\n        if review is None:\n            raise DomainError(\"There is no open review.\")", "        review = document.reviews.filter(status=Review.Status.OPEN).first()\n        if review is None:\n            raise DomainError(\"There is no open review.\")"),
    ("notifications: sent before the commit", S, "transaction.on_commit(lambda: send_notice.enqueue(user_ids=ids, subject=subject, body=body))", "send_notice.enqueue(user_ids=ids, subject=subject, body=body)"),
    ("notifications: one message with all the recipients", T,
     '    for user in get_user_model().objects.filter(pk__in=user_ids).exclude(email=""):\n        EmailMessage(subject=subject, body=body, from_email=settings.VAULT_FROM, to=[user.email]).send()\n        sent += 1',
     '    emails = [u.email for u in get_user_model().objects.filter(pk__in=user_ids).exclude(email="")]\n    if emails:\n        EmailMessage(subject=subject, body=body, from_email=settings.VAULT_FROM, to=emails).send()\n        sent = len(emails)'),
    ("model: more open reviews allowed", MIG2, '                condition=models.Q(("status", "open")),\n', ""),
    ("search: no iterative scan", SE, "cursor.execute(\"SET LOCAL hnsw.iterative_scan = 'relaxed_order'\")", "pass"),
    ("search: no permissions filter", SE, "                version__document__in=visible,\n", ""),
    ("search: the old versions too", SE, '                version__document__current_version=F("version"),\n', ""),
    ("search: no final reordering", SE, "results.sort(key=lambda c: (c.distance, c.pk))", "pass"),
    ("answer: the distance threshold is ignored", RAG, "results[0].distance > settings.RAG_MAX_DISTANCE", "False"),
    ("indexing: the chunks pile up", T, "        Chunk.objects.filter(version=version).delete()\n", "        pass\n"),
    ("migration: no way back", MIG3, "migrations.RunPython(text_into_first_version, version_into_text)", "migrations.RunPython(text_into_first_version, migrations.RunPython.noop)"),
    ("migration: wrong fingerprint", MIG3, "hash=hashlib.sha256(text.encode()).hexdigest(),", 'hash=hashlib.sha256(b"").hexdigest(),'),
    ("migration: the author is not copied", MIG3, "author_id=document.owner_id,", "author_id=None,"),
    ("theme: a white background in a corner", CSS, "button.primary { background: #1f6feb;", "button.primary { background: #ffffff;"),
    ("theme: the declaration to the browser is missing", BASE, '  <meta name="color-scheme" content="dark">\n', ""),
    ("theme: color-scheme removed from the CSS", CSS, "  color-scheme: dark;\n", ""),
    ("page: content not escaped", DETAIL, "{{ document.current_version.text }}</pre>", "{{ document.current_version.text|safe }}</pre>"),
    ("page: the HTMX errors are invisible", V, 'context["notices"] = list(messages.get_messages(request))', 'context["notices"] = []'),
    ("csp: the middleware is not in the list", CFG, '    "django.middleware.csp.ContentSecurityPolicyMiddleware",\n', ""),
    ("csp: inline scripts allowed", CFG, '"script-src": [CSP.SELF, CSP.NONCE],', '"script-src": [CSP.SELF, CSP.UNSAFE_INLINE],'),
]

originals = {}


def restore(*_):
    for rel, text in originals.items():
        (ROOT / rel).write_text(text)
    if _:
        sys.exit(1)


for sig in (signal.SIGTERM, signal.SIGINT):
    signal.signal(sig, restore)
atexit.register(restore)

check_only = "--check" in sys.argv
survivors = 0
for name, rel, old, new in MUTANTS:
    path = ROOT / rel
    originals.setdefault(rel, path.read_text())
    text = originals[rel]
    assert text.count(old) == 1, f"{name}: the pattern is found {text.count(old)} times"
    if check_only:
        continue
    path.write_text(text.replace(old, new))
    # the `pytest` script, not `python -m pytest`: the latter puts the current folder in sys.path
    cmd = [str(Path(sys.executable).parent / "pytest"), "-x", "-q", "-p", "no:cacheprovider"]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    path.write_text(text)
    if result.returncode == 0:
        survivors += 1
        print(f"ALIVE {name}", flush=True)
    else:
        print(f"OK    {name}", flush=True)
if not check_only:
    print(f"surviving mutants: {survivors} out of {len(MUTANTS)}")
