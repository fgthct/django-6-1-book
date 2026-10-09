import hashlib

from django.db import migrations
from django.utils.text import slugify


def text_into_first_version(apps, schema_editor):
    """Every prototype document becomes a document with one version, number 1.

    We use the *historical* models (apps.get_model), not those of documents.models: a
    migration must work with the shape the tables had at that moment.
    It doesn't touch the file system: imported versions have no file, only the text.
    """
    Document = apps.get_model("documents", "Document")
    Version = apps.get_model("documents", "Version")
    for document in Document.objects.filter(current_version=None).iterator():
        text = document.text or ""
        version = Version.objects.create(
            document=document,
            number=1,
            file_name=f"{slugify(document.title) or 'document'}.txt",
            text=text,
            hash=hashlib.sha256(text.encode()).hexdigest(),
            author_id=document.owner_id,
            note="Imported from the prototype",
        )
        document.current_version = version
        document.save(update_fields=["current_version"])


def version_into_text(apps, schema_editor):
    """The way back: the current version's text goes back into the old field."""
    Document = apps.get_model("documents", "Document")
    for document in Document.objects.exclude(current_version=None).select_related("current_version"):
        document.text = document.current_version.text
        document.save(update_fields=["text"])


class Migration(migrations.Migration):
    dependencies = [("documents", "0002_versions_reviews_chunks")]

    operations = [migrations.RunPython(text_into_first_version, version_into_text)]
