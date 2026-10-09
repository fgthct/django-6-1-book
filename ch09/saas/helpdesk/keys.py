import hashlib
import hmac
import secrets

from django.utils import timezone

from .models import ApiKey


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def create_key(member):
    """Returns the key's text: it is the only time it exists in clear."""
    prefix = secrets.token_hex(4)
    secret = secrets.token_urlsafe(32)
    text = f"ak_{prefix}_{secret}"
    ApiKey.objects.create(member=member, prefix=prefix, fingerprint=_fingerprint(text))
    return text


def verify(text):
    """The Member the key belongs to, or None."""
    parts = text.split("_", 2)
    if len(parts) != 3 or parts[0] != "ak":
        return None
    key = (
        ApiKey.objects.select_related("member__organization", "member__user")
        .filter(prefix=parts[1], revoked_at__isnull=True)
        .first()
    )
    if key is None or not hmac.compare_digest(key.fingerprint, _fingerprint(text)):
        return None
    return key.member


def revoke(text):
    parts = text.split("_", 2)
    return ApiKey.objects.filter(prefix=parts[1], revoked_at__isnull=True).update(revoked_at=timezone.now())
