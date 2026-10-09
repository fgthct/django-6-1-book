"""Who can do what on a document. Three levels and one rule: what you can't see doesn't exist."""

from django.core.exceptions import PermissionDenied

from .models import Access

NONE, READ, EDIT, OWNER = 0, 1, 2, 3  # OWNER (3) can't be granted by any Access


def level_of(user, document):
    if document.owner_id == user.pk:
        return OWNER
    level = Access.objects.filter(document=document, user=user).values_list("level", flat=True).first()
    return level or NONE


def require(user, document, minimum):
    if level_of(user, document) < minimum:
        raise PermissionDenied("insufficient permission on this document")
