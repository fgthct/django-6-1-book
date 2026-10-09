"""Break the code on purpose, one change at a time, and run every test after each change.

    python experiments/mutants.py                 # the complete suite
    python experiments/mutants.py --first-draft   # without the test added late
"""
import atexit
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
T = "campaigns/tasks.py"
L = "campaigns/limiter.py"
V = "campaigns/views.py"
VAL = "campaigns/validation.py"
IMP = "campaigns/importer.py"
TPL = "campaigns/templates/campaigns/detail.html"
MIG = "campaigns/migrations/0001_initial.py"

MUTANTS = [
    ("send: doesn't look at the status (double send)", T, 'if delivery.status != Delivery.Status.PENDING:\n            return "already handled"', 'if False:\n            return "already handled"'),
    ("send: one attempt fewer", T, "if delivery.attempts >= settings.CAMPAIGN_MAX_ATTEMPTS:", "if delivery.attempts >= settings.CAMPAIGN_MAX_ATTEMPTS - 1:"),
    ("send: wrong mailer", T, 'message.send(using="campaigns")', 'message.send(using="default")'),
    ("send: str.format on the text", T, 'delivery.campaign.body.replace("{name}", delivery.contact.name)', "delivery.campaign.body.format(name=delivery.contact.name)"),
    ("send: doesn't count the attempts", T, "delivery.attempts += 1", "delivery.attempts += 0"),
    ("send: linear wait", T, "2 ** (attempt - 1)", "attempt"),
    ("send: limit exceeded and doesn't postpone", T, 'if not limiter.allow("campaigns", settings.CAMPAIGN_SENDS_PER_SECOND):', "if False:"),
    ("send: retries without waiting for the commit", T, "transaction.on_commit(lambda: send_delivery.using(run_after=when).enqueue(delivery_id=delivery_id))", "send_delivery.using(run_after=when).enqueue(delivery_id=delivery_id)"),
    ("send: campaign closed too early", T, ").exclude(\n        still_pending\n    ).update(", ").update("),
    ("prepare: without ignore_conflicts", T, "        ignore_conflicts=True,\n", ""),
    ("prepare: inactive contacts too", T, "Contact.objects.filter(active=True)", "Contact.objects.all()"),
    ("prepare: ignores the campaign status", T, "if campaign.status != Campaign.Status.SENDING:\n        return 0", "if False:\n        return 0"),
    ("limiter: < instead of <=", L, "return counter <= maximum", "return counter < maximum"),
    ("limiter: counters that never expire", L, "pipe.expire(key, window * 2)", "pipe.persist(key)"),
    ("limiter: name ignored in the key", L, 'key = f"limit:{name}:{int(moment // window)}"', 'key = f"limit::{int(moment // window)}"'),
    ("view: unconditional start", V, "Campaign.objects.filter(pk=pk, status=Campaign.Status.DRAFT).update(", "Campaign.objects.filter(pk=pk).update("),
    ("view: enqueues right away, no commit", V, "transaction.on_commit(lambda: prepare_deliveries.enqueue(campaign_id=pk))", "prepare_deliveries.enqueue(campaign_id=pk)"),
    ("view: the percentage ignores the failed", V, 'done = c["sent"] + c["failed"]', 'done = c["sent"]'),
    ("template: polling always on", TPL, '{% if campaign.status == "sending" %}', "{% if True %}"),
    ("validation: no NFKC on the email", VAL, 'raw = unicodedata.normalize("NFKC", email).strip().lower()', "raw = email.strip().lower()"),
    ("validation: no punycode", VAL, 'ascii_domain = domain.encode("idna").decode("ascii")', "ascii_domain = domain"),
    ("validation: name not required", VAL, "elif not clean_name:", "elif False:"),
    ("import: duplicates not detected", IMP, "elif email in seen:", "elif False:"),
    ("import: subinterpreters without a path", IMP, "InterpreterPoolExecutor(initializer=site.addsitedir, initargs=(str(settings.BASE_DIR),))", "InterpreterPoolExecutor()"),
    ("import: the ones already there are not counted", IMP, "result.new = len(seen) - len(present)", "result.new = len(seen)"),
    ("recovery: ignores the deadline", T, "        due_at__lt=limit,\n", ""),
    ("recovery: requeues the closed ones too", T, "        status=Delivery.Status.PENDING,\n        campaign__status", "        campaign__status"),
    ("recovery: deadline not updated", T, "    Delivery.objects.filter(pk__in=pks).update(due_at=timezone.now())\n", "    pass\n"),
    ("model: no uniqueness of the delivery", MIG, '"constraints": [\n                    models.UniqueConstraint(\n                        fields=("campaign", "contact"), name="one_delivery_per_contact"\n                    )\n                ],', '"constraints": [],'),
]

LATE_TEST = "campaigns/tests/test_send.py::test_the_new_attempt_does_not_start_before_the_commit"

originals = {}


def restore(*_):
    for rel, text in originals.items():
        (ROOT / rel).write_text(text)
    if _:
        sys.exit(1)


for sig in (signal.SIGTERM, signal.SIGINT):
    signal.signal(sig, restore)
atexit.register(restore)

first_draft = "--first-draft" in sys.argv
survivors = 0
for name, rel, old, new in MUTANTS:
    path = ROOT / rel
    originals.setdefault(rel, path.read_text())
    text = originals[rel]
    assert text.count(old) == 1, f"{name}: the pattern is found {text.count(old)} times"
    path.write_text(text.replace(old, new))
    # the `pytest` script, not `python -m pytest`: the latter puts the current folder
    # in sys.path, and that would hide the subinterpreter trap
    cmd = [str(Path(sys.executable).parent / "pytest"), "-x", "-q", "-p", "no:cacheprovider"]
    if first_draft:
        cmd += ["--deselect", LATE_TEST]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    path.write_text(text)
    if result.returncode == 0:
        survivors += 1
        print(f"SURVIVED {name}")
    else:
        print(f"OK   {name}")
print(f"surviving mutants: {survivors} out of {len(MUTANTS)}")
