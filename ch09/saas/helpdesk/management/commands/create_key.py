from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from helpdesk import keys
from helpdesk.models import Member


class Command(BaseCommand):
    help = "Create an API key for a member: create_key <organization-slug> <email>. It is printed once."

    def add_arguments(self, parser):
        parser.add_argument("slug")
        parser.add_argument("email")

    def handle(self, *args, slug, email, **options):
        try:
            member = Member.objects.select_related("organization", "user").get(
                organization__slug=slug, user__email=email
            )
        except Member.DoesNotExist:
            raise CommandError("no such member") from None
        self.stdout.write(keys.create_key(member))
