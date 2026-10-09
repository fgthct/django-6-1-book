from django.contrib.postgres.search import SearchHeadline, SearchQuery, SearchRank
from django.db import models
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, ListView

from .forms import CommentForm
from .models import Article
from .templatetags.blog_extra import END, START


class ArticleListView(ListView):
    paginate_by = 6

    def get_queryset(self):
        queryset = (
            Article.objects.filter(published=True)
            .fetch_mode(models.FETCH_PEERS)
        )
        category = self.request.GET.get("category")
        if category:
            queryset = queryset.filter(category__slug=category)
        tag = self.request.GET.get("tag")
        if tag:
            queryset = queryset.filter(tags__contains=[tag])
        q = self.request.GET.get("q", "").strip()
        if q:
            query = SearchQuery(q, config="english", search_type="websearch")
            queryset = (
                queryset.filter(search=query)
                .annotate(
                    rank=SearchRank(F("search"), query),
                    excerpt=SearchHeadline(
                        "body",
                        query,
                        config="english",
                        start_sel=START,
                        stop_sel=END,
                        max_words=30,
                        min_words=15,
                    ),
                )
                .order_by("-rank", "-pk")
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        return context


class ArticleDetailView(DetailView):
    queryset = Article.objects.filter(published=True)
    context_object_name = "article"


class CommentCreateView(View):
    http_method_names = ["post"]

    def post(self, request, slug):
        article = get_object_or_404(Article, slug=slug, published=True)
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.article = article
            comment.save()
        return redirect(article)
