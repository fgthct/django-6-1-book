from django.conf import settings
from django.db import models
from pgvector.django import HnswIndex, VectorField


class Sentence(models.Model):
    text = models.CharField(max_length=300, unique=True)
    topic = models.CharField(max_length=40)
    embedding = VectorField(dimensions=settings.EMBEDDING_DIMENSIONS, null=True, blank=True)

    class Meta:
        ordering = ["topic", "pk"]

    def __str__(self) -> str:
        return self.text


class SamplePoint(models.Model):
    """Only for the index lab: synthetic vectors, not real texts."""

    group = models.PositiveSmallIntegerField()
    embedding = VectorField(dimensions=settings.EMBEDDING_DIMENSIONS)

    class Meta:
        indexes = [
            HnswIndex(
                name="samplepoint_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            )
        ]
