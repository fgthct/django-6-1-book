from django.contrib.postgres.search import SearchHeadline, SearchQuery, SearchRank, SearchVector
from django.db.models import F

from articles.models import Article


def search(text):
    query = SearchQuery(text, config="english", search_type="websearch")
    return (
        Article.objects.filter(search=query)
        .annotate(rank=SearchRank(F("search"), query))
        .order_by("-rank", "-pk")
    )


SEARCHES = [
    "volcanoes",
    "sicily",
    "sicilian",
    "etna",
    "etna -cable",
    '"greek theater"',
    "lava OR ricotta",
]

for text in SEARCHES:
    print(f"{text!r}:")
    for a in search(text):
        print(f"   {a.rank:.3f}  {a.title}")
