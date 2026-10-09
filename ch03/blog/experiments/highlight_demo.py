from django.contrib.postgres.search import SearchHeadline, SearchQuery

from articles.models import Article

query = SearchQuery("lava", config="english", search_type="websearch")

article = (
    Article.objects.filter(search=query)
    .annotate(
        excerpt=SearchHeadline(
            "body",
            query,
            config="english",
            start_sel="⟦",
            stop_sel="⟧",
            max_words=20,
            min_words=10,
        )
    )
    .order_by("pk")
    .first()
)

print(article.title)
print(article.excerpt)
