from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from helpdesk import tenant
from helpdesk.models import Member, Organization, Ticket

DEMO = [("acme", "Acme Inc"), ("rossi", "Rossi & Sons")]


class Command(BaseCommand):
    help = "Two organizations, three members each, 25 tickets each (password: demo)."

    def handle(self, *args, **options):
        User = get_user_model()
        for slug, name in DEMO:
            org, _ = Organization.objects.get_or_create(slug=slug, defaults={"name": name})
            members = {}
            for role, label in ((Member.Role.ADMIN, "admin"), (Member.Role.AGENT, "agent"), (Member.Role.READER, "reader")):
                email = f"{label}@{slug}.test"
                user, created = User.objects.get_or_create(username=f"{label}_{slug}", defaults={"email": email})
                if created:
                    user.set_password("demo")
                    user.save()
                members[label], _ = Member.objects.get_or_create(user=user, organization=org, defaults={"role": role})
            with tenant.tenant(org):
                if not Ticket.objects.exists():
                    for n in range(1, 26):
                        Ticket.objects.create(
                            title=f"{name}: issue {n}",
                            requester=f"customer{n}@example.test",
                            status=Ticket.Status.CLOSED if n % 4 == 1 else Ticket.Status.OPEN,
                            priority=(n % 3) + 1,
                            assigned=members["admin"] if n % 2 else members["agent"],
                        )
        self.stdout.write("done")
