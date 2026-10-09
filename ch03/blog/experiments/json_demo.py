from django.db.models import JSONNull

from articles.models import Article

Article.objects.create(title="T1", slug="t1", body="x", metadata=None)
Article.objects.create(title="T2", slug="t2", body="x", metadata=JSONNull())
Article.objects.create(title="T3", slug="t3", body="x", metadata={"minutes": 3})

tests = Article.objects.filter(slug__in=["t1", "t2", "t3"])

print("metadata__isnull=True  ->", list(tests.filter(metadata__isnull=True).values_list("slug", flat=True)))
print("metadata=JSONNull()    ->", list(tests.filter(metadata=JSONNull()).values_list("slug", flat=True)))

tests.delete()
