"""N+1 under the three fetch modes: 10 tickets, each assigned to a different member."""
import django

django.setup()
from django.contrib.auth import get_user_model  # noqa
from django.db import connection, models  # noqa
from django.test.utils import CaptureQueriesContext  # noqa

from helpdesk import tenant  # noqa
from helpdesk.models import Member, Organization, Ticket  # noqa

User = get_user_model()
org = Organization.objects.create(slug="lab", name="Lab")
try:
    with tenant.tenant(org):
        for n in range(10):
            user = User.objects.create(username=f"lab{n}", email=f"lab{n}@lab.test")
            member = Member.objects.create(user=user, organization=org)
            Ticket.objects.create(title=f"t{n}", requester="a@b.it", assigned=member)

    def distracted(queryset):
        """The code that forgets select_related."""
        return [t.assigned.user.email for t in queryset]

    def run(label, queryset):
        with CaptureQueriesContext(connection) as ctx:
            try:
                distracted(queryset)
                result = "ok"
            except Exception as e:
                result = f"{type(e).__name__}: {e}"
        print(f"{label:42}query: {len(ctx):2}   {result}")

    base = Ticket.unfiltered.filter(organization=org)
    run("FETCH_ONE (the usual behavior)", base.fetch_mode(models.FETCH_ONE))
    run("FETCH_PEERS", base.fetch_mode(models.FETCH_PEERS))
    run("FETCH_RAISE", base.fetch_mode(models.FETCH_RAISE))
    run("select_related + FETCH_RAISE", base.select_related("assigned__user").fetch_mode(models.FETCH_RAISE))
finally:
    Ticket.unfiltered.filter(organization=org).delete()
    Member.objects.filter(organization=org).delete()
    User.objects.filter(username__startswith="lab").delete()
    org.delete()
