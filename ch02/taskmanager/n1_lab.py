from django.core.exceptions import FieldFetchBlocked
from django.db import connection, models
from django.test.utils import CaptureQueriesContext

from todo.models import Task


def measure(description, queryset):
    with CaptureQueriesContext(connection) as context:
        names = [t.project.name for t in queryset]
    print(f"{description:<28} {len(names)} rows, queries: {len(context):>2}")


measure("FETCH_ONE (default)", Task.objects.all())
measure("FETCH_PEERS", Task.objects.fetch_mode(models.FETCH_PEERS))
measure("select_related", Task.objects.select_related("project"))

try:
    [t.project.name for t in Task.objects.fetch_mode(models.FETCH_RAISE)]
except FieldFetchBlocked as error:
    print("FETCH_RAISE:", error)
