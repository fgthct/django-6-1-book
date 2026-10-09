from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models
from django.urls import reverse


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.name


class Article(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.DB_SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    summary = models.CharField(max_length=300, blank=True)
    body = models.TextField()
    tags = ArrayField(models.CharField(max_length=30), default=list, blank=True)
    cover = models.ImageField(upload_to="covers/", blank=True)
    metadata = models.JSONField(null=True, blank=True)
    published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    search = models.GeneratedField(
        expression=(
            SearchVector("title", weight="A", config="english")
            + SearchVector("summary", weight="B", config="english")
            + SearchVector("body", weight="C", config="english")
        ),
        output_field=SearchVectorField(),
        db_persist=True,
    )

    class Meta:
        ordering = ["-published_at", "-pk"]
        indexes = [
            GinIndex(fields=["search"]),
            GinIndex(fields=["tags"]),
        ]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("articles:detail", kwargs={"slug": self.slug})


class Comment(models.Model):
    article = models.ForeignKey(
        Article, on_delete=models.DB_CASCADE, related_name="comments"
    )
    author = models.CharField(max_length=80)
    body = models.TextField()
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created", "pk"]

    def __str__(self) -> str:
        return f"{self.author}: {self.body[:30]}"
