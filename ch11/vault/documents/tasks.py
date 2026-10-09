from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.db import transaction
from django.tasks import task

from . import chunking
from .embedder import embed
from .models import Chunk, Version


@task
def send_notice(user_ids, subject, body):
    """One message per recipient, separately: nobody sees who else received it."""
    sent = 0
    for user in get_user_model().objects.filter(pk__in=user_ids).exclude(email=""):
        EmailMessage(subject=subject, body=body, from_email=settings.VAULT_FROM, to=[user.email]).send()
        sent += 1
    return sent


@task
def index_version(version_id):
    """Passages and vectors of a version. Idempotent: it deletes what exists and recreates it."""
    version = Version.objects.get(pk=version_id)
    passages = chunking.split(version.text)
    vectors = embed(passages) if passages else []
    with transaction.atomic():
        Chunk.objects.filter(version=version).delete()
        Chunk.objects.bulk_create(
            Chunk(version=version, position=n, text=text, embedding=vector)
            for n, (text, vector) in enumerate(zip(passages, vectors, strict=True), start=1)
        )
    return len(passages)
