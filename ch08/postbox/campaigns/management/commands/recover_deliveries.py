from datetime import timedelta

from django.core.management.base import BaseCommand

from campaigns.tasks import requeue_lost


class Command(BaseCommand):
    help = "Re-enqueue the deliveries that got lost (killed worker, lost task)."

    def add_arguments(self, parser):
        parser.add_argument("--minutes", type=float, default=5, help="how late counts as lost")

    def handle(self, *args, **options):
        n = requeue_lost(timedelta(minutes=options["minutes"]))
        self.stdout.write(f"{n} deliveries put back in the queue")
