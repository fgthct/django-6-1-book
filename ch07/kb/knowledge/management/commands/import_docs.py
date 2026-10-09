import hashlib
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from knowledge.chunking import split, to_embed
from knowledge.embedder import embed
from knowledge.models import Chunk, Document


class Command(BaseCommand):
    help = "Import the Markdown files of a folder (idempotent: only what changed is redone)."

    def add_arguments(self, parser):
        parser.add_argument("folder", nargs="?", default="knowledge/corpus")
        parser.add_argument("--force", action="store_true", help="redo everything")
        parser.add_argument(
            "--delete-orphans", action="store_true",
            help="delete the documents whose file no longer exists",
        )

    def handle(self, *args, folder, force, delete_orphans, **options):
        counts = {"new": 0, "updated": 0, "unchanged": 0}
        files = sorted(Path(folder).glob("*.md"))
        for f in files:
            counts[self.import_file(f, force)] += 1
        if delete_orphans:
            names = [f.name for f in files]
            deleted, _ = Document.objects.exclude(path__in=names).delete()
            self.stdout.write(f"{deleted} orphan documents deleted")
        self.stdout.write(
            f"{counts['new']} new, {counts['updated']} updated, {counts['unchanged']} unchanged"
        )

    def import_file(self, f: Path, force: bool) -> str:
        content = f.read_text(encoding="utf-8")
        fingerprint = hashlib.sha256(content.encode()).hexdigest()
        existing = Document.objects.filter(path=f.name).first()
        if existing and not force and existing.hash == fingerprint and self.up_to_date(existing):
            return "unchanged"

        title, pieces = split(content)
        vectors = embed([to_embed(title, p) for p in pieces])
        with transaction.atomic():
            doc, _ = Document.objects.update_or_create(
                path=f.name, defaults={"title": title or f.stem, "hash": fingerprint}
            )
            doc.chunks.all().delete()
            Chunk.objects.bulk_create(
                Chunk(document=doc, position=i, section=p.section, text=p.text,
                      embedding=v, model=settings.EMBEDDING_MODEL)
                for i, (p, v) in enumerate(zip(pieces, vectors))
            )
        return "updated" if existing else "new"

    def up_to_date(self, doc: Document) -> bool:
        """Is the document unchanged, and do its vectors come from the current model?"""
        return not doc.chunks.exclude(model=settings.EMBEDDING_MODEL).exists()
