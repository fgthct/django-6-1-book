"""The two traps of full-text search on the chunks."""
import django

django.setup()

from django.contrib.postgres.search import SearchQuery  # noqa: E402
from django.db import connection  # noqa: E402

from knowledge.models import Chunk  # noqa: E402
from knowledge.search import search_by_words  # noqa: E402

q = "How many vacation days do I get in a year?"
print(f"1. websearch, all words in AND : {len(list(search_by_words(q, 50, all_words=True)))} results")
print(f"   websearch, words in OR      : {len(list(search_by_words(q, 50)))} results")

# The second trap depends on the server's default text-search configuration.
# On this server it is 'english'; on many others (locale C, some images) it is 'simple'.
with connection.cursor() as cur:
    cur.execute("SHOW default_text_search_config")
    print(f"\nDefault configuration of this server: {cur.fetchone()[0]}")
    cur.execute("SET default_text_search_config = 'pg_catalog.simple'")
print("Now the same session, as on a server whose default is 'simple':")
print(f"2. filter(search='vacations')  : {Chunk.objects.filter(search='vacations').count()} results")
n = Chunk.objects.filter(search=SearchQuery("vacations", config="english")).count()
print(f"   filter(search=SearchQuery(..., config='english')): {n} results")
