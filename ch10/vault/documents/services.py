"""The product rules. Views, commands and tasks call only this module."""

import hashlib
from contextlib import contextmanager

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from . import permissions
from .models import Access, Document, Event, Participant, Review, Version
from .tasks import index_version, send_notice

MAX_REVIEWERS = settings.MAX_REVIEWERS


class DomainError(Exception):
    """A product rule that says no. The message is meant for the user."""


@contextmanager
def _files_to_clean_up():
    """If something goes wrong, the files already written to disk must not stay orphaned."""
    saved = []
    try:
        yield saved
    except BaseException:
        for name in saved:
            default_storage.delete(name)
        raise


def _read(file):
    """The bytes, the text and the fingerprint of an uploaded file. Only UTF-8 text, up to a maximum size."""
    raw = file.read()
    if len(raw) > settings.MAX_FILE_SIZE:
        raise DomainError(f"The file is too large (maximum {settings.MAX_FILE_SIZE:,} bytes).")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise DomainError("Only UTF-8 text files are accepted.") from None
    return raw, text, hashlib.sha256(raw).hexdigest()


def _event(user, document, kind, detail=""):
    Event.objects.create(document=document, user=user, kind=kind, detail=detail)


def _notify(users, subject, body):
    """Never inside the transaction: on rollback, we would announce something that didn't happen."""
    ids = [u.pk for u in users]
    if ids:
        transaction.on_commit(lambda: send_notice.enqueue(user_ids=ids, subject=subject, body=body))


def _new_version(document, user, file, note, saved):
    raw, text, digest = _read(file)
    last = document.versions.order_by("-number").first()
    version = Version(
        document=document,
        number=(last.number + 1) if last else 1,
        file_name=getattr(file, "name", "") or "document.txt",
        text=text,
        hash=digest,
        author=user,
        note=note,
    )
    version.file.save(version.file_name, ContentFile(raw), save=False)
    saved.append(version.file.name)
    version.save()
    document.current_version = version
    document.save(update_fields=["current_version"])
    transaction.on_commit(lambda: index_version.enqueue(version_id=str(version.pk)))
    return version


def create_document(user, title, file, note=""):
    with _files_to_clean_up() as saved, transaction.atomic():
        document = Document.objects.create(title=title.strip() or "Untitled", owner=user)
        _new_version(document, user, file, note, saved)
        _event(user, document, "created", document.title)
    return document


def upload_version(user, document, file, note=""):
    with _files_to_clean_up() as saved, transaction.atomic():
        # The lock on the document's row: two uploads at once don't get the same number.
        document = Document.objects.select_for_update().get(pk=document.pk)
        permissions.require(user, document, permissions.EDIT)
        if document.state == Document.State.IN_REVIEW:
            raise DomainError("The document is under review: cancel the review before uploading a new version.")
        current = document.current_version
        if current is not None and _read(file)[2] == current.hash:
            raise DomainError("The file is identical to the current version.")
        file.seek(0)
        version = _new_version(document, user, file, note, saved)
        if document.state == Document.State.APPROVED:
            document.state = Document.State.DRAFT  # a new version has to be approved again
            document.save(update_fields=["state"])
        _event(user, document, "new_version", f"v{version.number}: {note}")
    return version


def grant_access(user, document, target, level):
    with transaction.atomic():
        document = Document.objects.select_for_update().get(pk=document.pk)
        permissions.require(user, document, permissions.OWNER)
        if target.pk == document.owner_id:
            raise DomainError("The owner already has full access.")
        if level not in Access.Level.values:
            raise DomainError("Unknown access level.")
        Access.objects.update_or_create(document=document, user=target, defaults={"level": level})
        _event(user, document, "access_granted", f"{target}: {Access.Level(level).label}")


def revoke_access(user, document, target):
    with transaction.atomic():
        document = Document.objects.select_for_update().get(pk=document.pk)
        permissions.require(user, document, permissions.OWNER)
        taking_part = Participant.objects.filter(
            review__document=document, review__status=Review.Status.OPEN, user=target
        ).exists()
        if taking_part:
            raise DomainError("This person is a reviewer in the open review: cancel it first.")
        Access.objects.filter(document=document, user=target).delete()
        _event(user, document, "access_revoked", str(target))


def _close(review, status):
    review.status = status
    review.closed = timezone.now()
    review.save(update_fields=["status", "closed"])
    review.participants.filter(decision=Participant.Decision.PENDING).update(
        decision=Participant.Decision.SUPERSEDED
    )


@transaction.atomic
def send_for_review(user, document, reviewers, mode, message=""):
    """Only the owner chooses the reviewers, and only the owner."""
    document = Document.objects.select_for_update().get(pk=document.pk)
    permissions.require(user, document, permissions.OWNER)
    if document.state != Document.State.DRAFT:
        raise DomainError("Only a draft can be sent for review.")
    ids = [r.pk for r in reviewers]
    if not ids:
        raise DomainError("Choose at least one reviewer.")
    if len(set(ids)) != len(ids):
        raise DomainError("A reviewer appears twice.")
    if document.owner_id in ids:
        raise DomainError("You can't be a reviewer of your own documents.")
    if len(ids) > MAX_REVIEWERS:
        raise DomainError(f"At most {MAX_REVIEWERS} reviewers.")
    review = Review.objects.create(
        document=document, version=document.current_version, mode=mode, message=message
    )
    for order, reviewer in enumerate(reviewers, start=1):
        Participant.objects.create(review=review, user=reviewer, order=order)
        Access.objects.get_or_create(document=document, user=reviewer)  # whoever has to read, can read
    document.state = Document.State.IN_REVIEW
    document.save(update_fields=["state"])
    _event(user, document, "sent_for_review", f"{review.get_mode_display()}: " + ", ".join(map(str, reviewers)))
    to_notify = reviewers[:1] if mode == Review.Mode.SEQUENTIAL else reviewers
    _notify(to_notify, f"Review requested: {document.title}",
            f"{user} asks you to review “{document.title}” (version {document.current_version.number}).\n\n{message}")
    return review


@transaction.atomic
def decide(user, document, approve, comment=""):
    # The same lock as "send" and "upload": two reviewers pressing together are put in line.
    document = Document.objects.select_for_update().get(pk=document.pk)
    review = document.reviews.filter(status=Review.Status.OPEN).first()
    if review is None:
        raise DomainError("There is no open review (perhaps it has already been concluded).")
    mine = review.participants.filter(user=user).first()
    if mine is None:
        raise PermissionDenied("You are not a reviewer of this document.")
    if mine.decision != Participant.Decision.PENDING:
        raise DomainError("You have already decided.")
    if review.mode == Review.Mode.SEQUENTIAL:
        next_up = review.participants.filter(decision=Participant.Decision.PENDING).first()
        if next_up.pk != mine.pk:
            raise DomainError("It is not your turn yet.")
    if not approve and not comment.strip():
        raise DomainError("To send a document back you need to write a comment.")

    mine.decision = Participant.Decision.APPROVED if approve else Participant.Decision.SENT_BACK
    mine.comment = comment
    mine.decided_at = timezone.now()
    mine.save()
    owner = document.owner
    if not approve:
        _close(review, Review.Status.SENT_BACK)
        document.state = Document.State.DRAFT
        document.save(update_fields=["state"])
        _event(user, document, "sent_back", comment)
        _notify([owner], f"Sent back to draft: {document.title}", f"{user} sent the document back.\n\n{comment}")
        return review
    _event(user, document, "approved", comment)
    still = review.participants.filter(decision=Participant.Decision.PENDING)
    if review.mode == Review.Mode.FREE or not still.exists():
        _close(review, Review.Status.APPROVED)
        document.state = Document.State.APPROVED
        document.save(update_fields=["state"])
        _notify([owner], f"Approved: {document.title}", f"{user} approved the document.")
    else:
        next_user = still.first().user
        _notify([next_user], f"Your turn: {document.title}", f"{user} approved. It is now your turn.\n\n{review.message}")
    return review


def cancel_review(user, document):
    with transaction.atomic():
        document = Document.objects.select_for_update().get(pk=document.pk)
        permissions.require(user, document, permissions.OWNER)
        review = document.reviews.filter(status=Review.Status.OPEN).first()
        if review is None:
            raise DomainError("There is no open review.")
        _close(review, Review.Status.CANCELLED)
        document.state = Document.State.DRAFT
        document.save(update_fields=["state"])
        _event(user, document, "review_cancelled")
