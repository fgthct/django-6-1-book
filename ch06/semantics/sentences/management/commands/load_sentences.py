from django.core.management.base import BaseCommand

from sentences.corpus import CORPUS
from sentences.embedder import embed
from sentences.models import Sentence


class Command(BaseCommand):
    help = "Load the sample sentences and compute their embeddings (idempotent)."

    def handle(self, *args, **options):
        for topic, texts in CORPUS.items():
            for text in texts:
                Sentence.objects.get_or_create(text=text, defaults={"topic": topic})
        to_do = list(Sentence.objects.filter(embedding=None))
        if to_do:
            vectors = embed([s.text for s in to_do])
            for sentence, vector in zip(to_do, vectors, strict=True):
                sentence.embedding = vector
            Sentence.objects.bulk_update(to_do, ["embedding"])
        self.stdout.write(f"{Sentence.objects.count()} sentences, {len(to_do)} embeddings computed.")
