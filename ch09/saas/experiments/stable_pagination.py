"""25 tickets with only three distinct priorities, paged ten at a time, three times over."""
import django

django.setup()
from django.db.models import F  # noqa
from django.utils import timezone  # noqa

from helpdesk import tenant  # noqa
from helpdesk.models import Organization, Ticket  # noqa

org = Organization.objects.get(slug="acme")


def walk(queryset):
    seen = []
    for offset in range(0, 25, 10):
        seen.extend(t.pk for t in queryset[offset : offset + 10])
    return seen


with tenant.tenant(org):
    print(f"tickets of the tenant: {Ticket.objects.count()}")
    cases = [
        ("order_by('priority')", lambda: Ticket.objects.order_by("priority")),
        ("order_by('priority', 'pk')", lambda: Ticket.objects.order_by("priority", "pk")),
        ("default ordering", lambda: Ticket.objects.all()),
    ]
    for label, make in cases:
        out = f"{label:30}totally_ordered={str(make().totally_ordered):6} "
        for lap in range(1, 4):
            rows = walk(make())
            out += f"lap {lap}: {len(rows)} rows, {len(set(rows))} distinct; "
            # between one lap and the next we "touch" the rows, like a live system would
            Ticket.objects.update(status=F("status"))
        print(out.rstrip())
