import django

django.setup()
from django.db.models import Count  # noqa

from helpdesk.models import CspViolation  # noqa

rows = (
    CspViolation.objects.values("report_only", "directive", "blocked_resource")
    .annotate(n=Count("pk"))
    .order_by("report_only", "directive", "blocked_resource")
)
for r in rows:
    kind = "report-only" if r["report_only"] else "blocked"
    print(f"{kind:13}{r['directive']:29}{r['blocked_resource']:23}x{r['n']}")
