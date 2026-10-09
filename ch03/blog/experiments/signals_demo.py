from articles import signals
from articles.models import Article, Comment

article = Article.objects.create(title="Test", slug="signals-test", body="x")
c1 = Comment.objects.create(article=article, author="A", body="one")
Comment.objects.create(article=article, author="B", body="two")
Comment.objects.create(article=article, author="C", body="three")

signals.deleted_comments.clear()
c1.delete()
print("after comment.delete():  signals received =", len(signals.deleted_comments))

signals.deleted_comments.clear()
article.delete()
print("after article.delete():  signals received =", len(signals.deleted_comments))
print("comments left for the article:", Comment.objects.filter(article_id=article.pk).count())
