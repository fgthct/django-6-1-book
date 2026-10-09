from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from documents import services
from documents.models import Document

USERS = [
    ("marta", "Marta", "Bianchi"),
    ("luca", "Luca", "Neri"),
    ("giulia", "Giulia", "Verdi"),
    ("paolo", "Paolo", "Gialli"),
]

POLICY = (
    "Every employee is entitled to twenty-six days of paid vacation per year.\n\n"
    "Vacation days must be requested at least two weeks in advance through the manager, "
    "and up to five unused days can be carried over to the following year.\n\n"
    "Public holidays are not counted as vacation days."
)
REPORT = "Revenue grew in the third quarter.\n\nThe figures are final."


class Command(BaseCommand):
    help = "Create four demo users (password: password) and two documents. Development only."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("create_demo creates users with a known password: use it only with DEBUG=1.")
        User = get_user_model()
        users = {}
        for username, first, last in USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"first_name": first, "last_name": last, "email": f"{username}@example.test"},
            )
            if created:
                user.set_password("password")
                user.save()
            users[username] = user
        for title, text, name in [
            ("Vacation policy", POLICY, "vacation-policy.txt"),
            ("Quarterly report", REPORT, "report.txt"),
        ]:
            if not Document.objects.filter(title=title, owner=users["marta"]).exists():
                file = ContentFile(text.encode(), name=name)
                services.create_document(users["marta"], title, file)
        self.stdout.write("Demo ready: marta, luca, giulia, paolo (password “password”).")
