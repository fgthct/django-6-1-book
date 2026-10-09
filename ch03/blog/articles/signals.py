from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Comment

deleted_comments: list[int] = []


@receiver(post_delete, sender=Comment)
def record_deletion(sender, instance, **kwargs):
    deleted_comments.append(instance.pk)
