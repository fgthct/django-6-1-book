from django.core.management.base import BaseCommand

from sentences.search import search_by_meaning, search_by_words


class Command(BaseCommand):
    help = "Search the sentences by meaning (and, with --compare, by words too)."

    def add_arguments(self, parser):
        parser.add_argument("question")
        parser.add_argument("--compare", action="store_true")
        parser.add_argument("--limit", type=int, default=5)

    def handle(self, *args, **options):
        question, limit = options["question"], options["limit"]
        self.stdout.write(f"Question: {question}")
        self.stdout.write("By meaning (cosine distance):")
        for s in search_by_meaning(question, limit):
            self.stdout.write(f"  {s.distance:.3f}  [{s.topic}] {s.text}")
        if options["compare"]:
            self.stdout.write("")
            self.stdout.write("By words (full-text, config english):")
            found = list(search_by_words(question, limit))
            if not found:
                self.stdout.write("  (no results)")
            for s in found:
                self.stdout.write(f"  {s.rank:.3f}  [{s.topic}] {s.text}")
