import time

import redis
from django.conf import settings


def _client() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL)


def allow(name: str, maximum: int, window: int = 1, *, now: float | None = None) -> bool:
    """True if this send may go ahead, False if the current window is already full.

    Fixed window: one counter for every second (`INCR`) that Redis deletes
    by itself (`EXPIRE`). Simple and atomic, so it works across several
    processes at once. Its known flaw: across two windows up to
    2 × maximum sends can go through in an instant.
    """
    moment = time.time() if now is None else now
    key = f"limit:{name}:{int(moment // window)}"
    pipe = _client().pipeline()
    pipe.incr(key)
    pipe.expire(key, window * 2)
    counter, _ = pipe.execute()
    return counter <= maximum
