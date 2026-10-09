from django.contrib.postgres.search import SearchQuery
from django.db.models import JSONNull

from articles.models import Article

from .helpers import make_article


def test_str(articles):
    assert str(articles["etna"]) == "Climbing Etna"


def test_tags_are_a_list(db):
    article = make_article("t", "T", "x")
    assert article.tags == []
    article.tags.append("a")
    assert make_article("u", "U", "x").tags == []


def test_default_ordering_is_deterministic(db):
    assert Article.objects.all().totally_ordered is True


def test_the_search_vector_updates_itself(articles):
    etna = articles["etna"]
    zebra = SearchQuery("zebra", config="english")
    assert not Article.objects.filter(pk=etna.pk, search=zebra).exists()
    etna.title = "Zebra crossing"
    etna.save()
    assert Article.objects.filter(pk=etna.pk, search=zebra).exists()


def test_json_null_and_sql_null_are_different(db):
    make_article("j1", "J1", "x").metadata is None
    a = Article.objects.create(title="J2", slug="j2", body="x", metadata=JSONNull())
    b = Article.objects.create(title="J3", slug="j3", body="x", metadata=None)
    assert list(Article.objects.filter(metadata=JSONNull())) == [a]
    assert b in Article.objects.filter(metadata__isnull=True)
    assert a not in Article.objects.filter(metadata__isnull=True)
