"""Break the code on purpose, one change at a time, and run every test after each change.

    python experiments/mutants.py                 # the complete suite
    python experiments/mutants.py --first-draft   # without the five tests added late
    python experiments/mutants.py --check         # only verify that every pattern is found
"""
import atexit
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEN = "helpdesk/tenant.py"
M = "helpdesk/models.py"
MW = "helpdesk/middleware.py"
S = "helpdesk/services.py"
T = "helpdesk/tasks.py"
A = "helpdesk/api.py"
K = "helpdesk/keys.py"
V = "helpdesk/views.py"
CFG = "config/settings.py"
TPL = "helpdesk/templates/helpdesk/ticket.html"
MIG = "helpdesk/migrations/0001_initial.py"

MUTANTS = [
    ("manager: doesn't filter", M, ".filter(organization=tenant.current()).fetch_mode(mode)", ".fetch_mode(mode)"),
    ("manager: without a tenant returns everything", M,
     "return super().get_queryset().filter(organization=tenant.current()).fetch_mode(mode)",
     "qs = super().get_queryset().fetch_mode(mode)\n        org = tenant.current_or_none()\n        return qs if org is None else qs.filter(organization=org)"),
    ("manager: ignores the fetch mode", M, ".filter(organization=tenant.current()).fetch_mode(mode)", ".filter(organization=tenant.current())"),
    ("write: accepts another tenant", M, "elif self.organization_id != current.pk:", "elif False:"),
    ("write: doesn't set the tenant", M, "            self.organization = current\n", "            pass\n"),
    ("ticket: incomplete ordering", M, 'ordering = ["-created", "-id"]', 'ordering = ["-created"]'),
    ("model: no one-role-per-organization constraint", MIG,
     'migrations.AddConstraint(\n            model_name="member",\n            constraint=models.UniqueConstraint(\n                fields=("user", "organization"), name="one_role_per_organization"\n            ),\n        ),\n', ""),
    ("organization: the mailer is not validated", M, "if self.mailer not in mailers:", "if False:"),
    ("middleware: no membership check", MW, 'raise PermissionDenied("You are not a member of this organization") from None', "pass"),
    ("middleware: unknown subdomain ignored", MW, 'raise Http404("Unknown organization") from None', "organization = None"),
    ("middleware: the context is never closed", MW, "with tenant.tenant() as context:", "context = tenant.tenant().__enter__()\n        if True:"),
    ("tenant: contexts don't nest", TEN, "_context.reset(token)", "_context.set(None)"),
    ("services: role not checked", S, "if not member.can(minimum_role):", "if False:"),
    ("services: assignee from another tenant", S, "if assignee is not None and assignee.organization_id != ticket.organization_id:", "if False:"),
    ("services: notification before the commit", S,
     "    transaction.on_commit(\n        lambda: notify_new_ticket.enqueue(\n            organization_id=str(ticket.organization_id), ticket_id=str(ticket.pk)\n        )\n    )\n",
     "    notify_new_ticket.enqueue(organization_id=str(ticket.organization_id), ticket_id=str(ticket.pk))\n"),
    ("services: free status", S, "if status not in Ticket.Status.values:", "if False:"),
    ("notifications: wrong mailer", T, ".send(using=organization.mailer)", '.send(using="default")'),
    ("notifications: the task doesn't reopen the tenant", T, "with tenant.tenant(organization):", "with tenant.tenant():"),
    ("notifications: recipients of every role", T, "Member.objects.filter(organization=organization, role=Member.Role.ADMIN)", "Member.objects.filter(organization=organization)"),
    ("api: key valid on every subdomain", A, "if request.organization is not None and request.organization != member.organization:", "if False:"),
    ("api: tenant not activated", A, "tenant.activate(member.organization)", "pass"),
    ("api: unchecked pagination", A, "@paginate(SafePagination)", "@paginate(LimitOffsetPagination)"),
    ("api: assignee searched among all tenants", A, "Member.objects.get(pk=data.member_id, organization=request.member.organization)", "Member.objects.get(pk=data.member_id)"),
    ("api: list without select_related", A, '    qs = Ticket.objects.select_related("assigned__user")\n    if status:', "    qs = Ticket.objects.all()\n    if status:"),
    ("api: public docs", A, "docs_url=None", 'docs_url="/docs"'),
    ("keys: fingerprint not verified", K, "if key is None or not hmac.compare_digest(key.fingerprint, _fingerprint(text)):", "if key is None:"),
    ("keys: revoked keys accepted", K, ".filter(prefix=parts[1], revoked_at__isnull=True)\n        .first()", ".filter(prefix=parts[1])\n        .first()"),
    ("keys: the key itself is stored", K, "fingerprint=_fingerprint(text))", "fingerprint=text[:64])"),
    ("view: ticket looked up without the filter", V, 'get_object_or_404(Ticket.objects.select_related("assigned__user"), pk=pk)', 'get_object_or_404(Ticket.unfiltered.select_related("assigned__user"), pk=pk)'),
    ("view: dashboard list without select_related", V, '    qs = Ticket.objects.select_related("assigned__user")\n    if status in', "    qs = Ticket.objects.all()\n    if status in"),
    ("view: the root no longer goes to the dashboard", V, 'return redirect("dashboard")', "pass"),
    ("csp: unsafe-inline in the styles", CFG, '"style-src": [CSP.SELF],\n    "img-src": [CSP.SELF, "data:"],', '"style-src": [CSP.SELF, CSP.UNSAFE_INLINE],\n    "img-src": [CSP.SELF, "data:"],'),
    ("csp: no nonce in the scripts", CFG, '"script-src": [CSP.SELF, CSP.NONCE],\n    "style-src": [CSP.SELF],\n    "img-src": [CSP.SELF, "data:"],', '"script-src": [CSP.SELF],\n    "style-src": [CSP.SELF],\n    "img-src": [CSP.SELF, "data:"],'),
    ("csp: no frame-ancestors", CFG, '    "frame-ancestors": [CSP.NONE],\n', ""),
    ("csp: the report requires the CSRF token", V, "@csrf_exempt  # it is sent by the browser, not by one of our forms: it can't have the token\n", ""),
    ("csp: no limit on the body", V, "if len(request.body) > BODY_LIMIT:", "if False:"),
    ("csp: fields not truncated", V, 'return (value or "")[:length]', 'return value or ""'),
    ("csp: no cap of 20 reports", V, "saved[:20]", "saved"),
    ("csp: the middleware is not in the list", CFG, '    "django.middleware.csp.ContentSecurityPolicyMiddleware",\n', ""),
    ("template: an inline onclick on a button", TPL, '<button type="submit">Send</button>', '<button type="submit" onclick="void 0">Send</button>'),
]

LATE_TESTS = [
    "helpdesk/tests/test_isolation.py::test_the_fetch_mode_raise_rule_is_active",
    "helpdesk/tests/test_rules.py::test_the_assignee_must_belong_to_the_same_organization",
    "helpdesk/tests/test_web.py::test_the_root_leads_to_the_dashboard",
    "helpdesk/tests/test_api.py::test_on_the_main_domain_the_key_alone_chooses_the_tenant",
    "helpdesk/tests/test_api.py::test_the_list_endpoint_refuses_an_incomplete_ordering",
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

first_draft = "--first-draft" in sys.argv
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
    if first_draft:
        for test in LATE_TESTS:
            cmd += ["--deselect", test]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    path.write_text(text)
    if result.returncode == 0:
        survivors += 1
        print(f"SURVIVED {name}", flush=True)
    else:
        print(f"OK   {name}", flush=True)
if not check_only:
    print(f"surviving mutants: {survivors} out of {len(MUTANTS)}")
