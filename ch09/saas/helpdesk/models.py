from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import mailers
from django.db import models
from django.db.models.functions import UUID7

from . import tenant


class Organization(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    mailer = models.CharField(max_length=30, default="default")

    def __str__(self):
        return self.name

    def clean(self):
        if self.mailer not in mailers:
            raise ValidationError({"mailer": f"The mailer “{self.mailer}” does not exist in MAILERS."})


class Member(models.Model):
    """A user inside an organization, with their role. This table is "global" too."""

    class Role(models.IntegerChoices):
        READER = 1, "Reader"
        AGENT = 2, "Agent"
        ADMIN = 3, "Administrator"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="members")
    role = models.IntegerField(choices=Role, default=Role.AGENT)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "organization"], name="one_role_per_organization"),
        ]

    def __str__(self):
        return f"{self.user} @ {self.organization.slug}"

    def can(self, minimum_role):
        return self.role >= minimum_role


class TenantManager(models.Manager):
    """The default manager of the tenant models: it *fails closed*.

    Without an active tenant it raises MissingTenant instead of returning everything.
    """

    def get_queryset(self):
        mode = getattr(models, settings.FETCH_MODE)
        return super().get_queryset().filter(organization=tenant.current()).fetch_mode(mode)


class TenantModel(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, editable=False)

    objects = TenantManager()
    unfiltered = models.Manager()  # for administration and commands: use with awareness

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        current = tenant.current()
        if self.organization_id is None:
            self.organization = current
        elif self.organization_id != current.pk:
            raise PermissionError("writing to a tenant other than the active one")
        super().save(*args, **kwargs)


class Ticket(TenantModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        CLOSED = "closed", "Closed"

    class Priority(models.IntegerChoices):
        LOW = 1, "Low"
        NORMAL = 2, "Normal"
        HIGH = 3, "High"

    id = models.UUIDField(primary_key=True, db_default=UUID7(), editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    requester = models.EmailField()
    status = models.CharField(max_length=20, choices=Status, default=Status.OPEN)
    priority = models.IntegerField(choices=Priority, default=Priority.NORMAL)
    assigned = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        # The full ordering: “created” can repeat, “id” cannot.
        ordering = ["-created", "-id"]
        indexes = [models.Index(fields=["organization", "status", "-created"], name="ticket_org_status_created")]


class Comment(TenantModel):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(Member, null=True, on_delete=models.SET_NULL, related_name="+")
    body = models.TextField()
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created", "id"]


class ApiKey(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="api_keys")
    prefix = models.CharField(max_length=8, db_index=True)
    fingerprint = models.CharField(max_length=64)
    created = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)


class CspViolation(models.Model):
    """A report sent by the browser when the policy blocks (or would block) something."""

    host = models.CharField(max_length=255)
    directive = models.CharField(max_length=100, blank=True)
    blocked_resource = models.CharField(max_length=500, blank=True)
    document = models.CharField(max_length=500, blank=True)
    report_only = models.BooleanField(default=False)
    received = models.DateTimeField(auto_now_add=True)
