from django.db import models


class Contact(models.Model):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["pk"]

    def __str__(self) -> str:
        return self.email


class Campaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENDING = "sending", "Sending"
        COMPLETED = "completed", "Completed"

    subject = models.CharField(max_length=200)
    body = models.TextField(help_text="Use {name} for the recipient's name.")
    status = models.CharField(max_length=12, choices=Status, default=Status.DRAFT)
    created = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created", "-pk"]
        verbose_name_plural = "campaigns"

    def __str__(self) -> str:
        return self.subject


class Delivery(models.Model):
    """One message for one recipient: the row that tells what happened."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="deliveries")
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="deliveries")
    status = models.CharField(max_length=10, choices=Status, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    # When the send task should have run: this is how we find the ones that got lost.
    due_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["pk"]
        verbose_name_plural = "deliveries"
        constraints = [
            models.UniqueConstraint(fields=["campaign", "contact"], name="one_delivery_per_contact"),
        ]
        indexes = [models.Index(fields=["campaign", "status"], name="delivery_campaign_status")]
