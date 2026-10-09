from django.db import models


class Note(models.Model):
    text = models.CharField(max_length=100)
    data = models.JSONField(default=dict)
