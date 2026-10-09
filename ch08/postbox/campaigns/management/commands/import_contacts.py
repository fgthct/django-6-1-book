from django.core.management.base import BaseCommand

from campaigns.importer import import_csv


class Command(BaseCommand):
    help = "Import and validate a CSV of contacts (email,name), in parallel."

    def add_arguments(self, parser):
        parser.add_argument("path")

    def handle(self, *args, path, **options):
        r = import_csv(path)
        self.stdout.write(
            f"{r.new} new, {r.already_present} already present, {r.rejected} rejected, "
            f"{r.duplicates_in_file} duplicates in the file"
        )
        for example in r.rejected_examples:
            self.stdout.write(f"  rejected: {example}")
