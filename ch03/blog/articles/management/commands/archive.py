from pathlib import Path

from django.core.management.base import BaseCommand

from articles.archive import write_archive


class Command(BaseCommand):
    help = "Archive the published articles to a Zstandard-compressed JSON file."

    def add_arguments(self, parser):
        parser.add_argument("--destination", default="archive.json.zst")

    def handle(self, *args, **options):
        path = Path(options["destination"])
        count = write_archive(path)
        self.stdout.write(f"{count} articles archived to {path} ({path.stat().st_size} bytes)")
