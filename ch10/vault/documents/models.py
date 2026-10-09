from django.conf import settings
from django.db import models
from django.db.models import Exists, OuterRef, Q
from django.db.models.functions import UUID7
from pgvector.django import HnswIndex, VectorField


class DocumentQuerySet(models.QuerySet):
    def visible_to(self, user):
        """The documents *this* user can see: their own, or one they have an access to."""
        return self.filter(
            Q(owner=user)
            | Exists(Access.objects.filter(document=OuterRef("pk"), user=user))
        )


class Document(models.Model):
    class State(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_REVIEW = "in_review", "In review"
        APPROVED = "approved", "Approved"

    id = models.UUIDField(primary_key=True, db_default=UUID7(), editable=False)
    title = models.CharField(max_length=200)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="documents")
    state = models.CharField(max_length=20, choices=State, default=State.DRAFT)
    current_version = models.ForeignKey("Version", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created = models.DateTimeField(auto_now_add=True)

    objects = DocumentQuerySet.as_manager()

    class Meta:
        ordering = ["-created", "-id"]

    def __str__(self):
        return self.title


class Version(models.Model):
    """A version is immutable: to change a document you create another one."""

    id = models.UUIDField(primary_key=True, db_default=UUID7(), editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveIntegerField()
    file = models.FileField(upload_to="versions/%Y/%m/", blank=True)
    file_name = models.CharField(max_length=200)
    text = models.TextField()
    hash = models.CharField(max_length=64)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    note = models.CharField(max_length=200, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-number"]
        constraints = [models.UniqueConstraint(fields=["document", "number"], name="one_version_per_number")]

    def __str__(self):
        return f"{self.document.title} v{self.number}"


class Access(models.Model):
    """Who, besides the owner, can read (level 1) or edit (level 2) a document."""

    class Level(models.IntegerChoices):
        READ = 1, "Read"
        EDIT = 2, "Edit"

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="accesses")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    level = models.IntegerField(choices=Level, default=Level.READ)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["document", "user"], name="one_access_per_user")]


class Review(models.Model):
    """An approval request for *one* version."""

    class Mode(models.TextChoices):
        SEQUENTIAL = "sequential", "In sequence"
        FREE = "free", "Free"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        APPROVED = "approved", "Approved"
        SENT_BACK = "sent_back", "Sent back"
        CANCELLED = "cancelled", "Cancelled"

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="reviews")
    version = models.ForeignKey(Version, on_delete=models.PROTECT, related_name="+")
    mode = models.CharField(max_length=20, choices=Mode, default=Mode.SEQUENTIAL)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status, default=Status.OPEN)
    created = models.DateTimeField(auto_now_add=True)
    closed = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created", "-id"]
        constraints = [
            # At most one open review per document: the database guarantees it, not the code.
            models.UniqueConstraint(
                fields=["document"], condition=Q(status="open"), name="one_open_review_per_document"
            )
        ]


class Participant(models.Model):
    """A reviewer inside a review, with their turn (`order`), their decision and their comment."""

    class Decision(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        SENT_BACK = "sent_back", "Sent back"
        SUPERSEDED = "superseded", "Superseded"

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    order = models.PositiveSmallIntegerField()
    decision = models.CharField(max_length=20, choices=Decision, default=Decision.PENDING)
    comment = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(fields=["review", "user"], name="one_participant_per_user"),
            models.UniqueConstraint(fields=["review", "order"], name="one_participant_per_turn"),
        ]


class Event(models.Model):
    """The activity log: it is appended to, never modified."""

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="events")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    kind = models.CharField(max_length=40)
    detail = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created", "id"]


class Chunk(models.Model):
    """The passages of a version, with their vector, for the search."""

    id = models.UUIDField(primary_key=True, db_default=UUID7(), editable=False)
    version = models.ForeignKey(Version, on_delete=models.CASCADE, related_name="chunks")
    position = models.PositiveSmallIntegerField()
    text = models.TextField()
    embedding = VectorField(dimensions=settings.EMBEDDING_DIMENSIONS, null=True, blank=True)

    class Meta:
        ordering = ["version", "position"]
        constraints = [models.UniqueConstraint(fields=["version", "position"], name="one_chunk_per_position")]
        indexes = [
            HnswIndex(
                name="chunk_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            )
        ]
