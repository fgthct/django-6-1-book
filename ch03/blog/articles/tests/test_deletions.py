from articles import signals
from articles.models import Comment


def test_deleting_a_comment_sends_the_signal(articles):
    comment = Comment.objects.create(article=articles["etna"], author="A", body="x")
    signals.deleted_comments.clear()
    comment.delete()
    assert len(signals.deleted_comments) == 1


def test_db_cascade_deletes_the_comments_but_sends_no_signals(articles):
    etna = articles["etna"]
    for author in ("A", "B", "C"):
        Comment.objects.create(article=etna, author=author, body="x")
    signals.deleted_comments.clear()

    etna.delete()

    assert Comment.objects.filter(author__in=["A", "B", "C"]).count() == 0
    assert signals.deleted_comments == []


def test_db_set_null_clears_the_category(articles, categories):
    categories["food"].delete()
    articles["cannolo"].refresh_from_db()
    assert articles["cannolo"].category is None
