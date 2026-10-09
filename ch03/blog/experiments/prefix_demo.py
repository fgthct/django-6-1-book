from django.contrib.postgres.search import Lexeme, SearchQuery

from articles.models import Article

query = SearchQuery(Lexeme("sicil", prefix=True), config="english", search_type="raw")

for article in Article.objects.filter(search=query):
    print(article.title)
