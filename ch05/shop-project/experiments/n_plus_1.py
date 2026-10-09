import asyncio
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import connection, models  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

from shop.models import Product  # noqa: E402


def measure(title, function):
    with CaptureQueriesContext(connection) as q:
        try:
            result = function()
        except Exception as error:
            result = f"{type(error).__name__}"
    print(f"{title:<34} queries: {len(q):>2}   {result}")


def names(queryset):
    return len({p.category.name for p in queryset})


measure("naive", lambda: names(Product.objects.all()))
measure("select_related('category')", lambda: names(Product.objects.select_related("category")))
measure("fetch_mode(FETCH_PEERS)", lambda: names(Product.objects.fetch_mode(models.FETCH_PEERS)))
measure("fetch_mode(FETCH_RAISE)", lambda: names(Product.objects.fetch_mode(models.FETCH_RAISE)))


async def in_async():
    return len({p.category.name async for p in Product.objects.fetch_mode(models.FETCH_PEERS)})


try:
    asyncio.run(in_async())
except Exception as error:
    print(f"FETCH_PEERS in an async loop       {type(error).__name__}: {error}")
