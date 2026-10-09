from datetime import datetime, timedelta, timezone

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import F

from articles.models import Article


def make_article(slug, title, body, *, summary="", tags=None, category=None,
                 published=True, day=0):
    return Article.objects.create(
        slug=slug,
        title=title,
        body=body,
        summary=summary,
        tags=tags or [],
        category=category,
        published=published,
        published_at=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc) + timedelta(days=day)
        if published else None,
    )


def search(text):
    query = SearchQuery(text, config="english", search_type="websearch")
    return (
        Article.objects.filter(search=query)
        .annotate(rank=SearchRank(F("search"), query))
        .order_by("-rank", "-pk")
    )


def slugs(queryset):
    return [a.slug for a in queryset]
