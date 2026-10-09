from django.contrib.postgres.search import SearchQuery
from django.db import connection

from articles.models import Article

query = SearchQuery("etna", config="english", search_type="websearch")
queryset = Article.objects.filter(search=query)

with connection.cursor() as cursor:
    # with few rows PostgreSQL prefers to read the whole table:
    # to see the index we discourage that, just for this experiment
    cursor.execute("SET enable_seqscan = off")
    print(queryset.explain())
