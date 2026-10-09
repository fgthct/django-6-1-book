from django.db import OperationalError, connection
from django.db.migrations.executor import MigrationExecutor
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health(request):
    """Liveness: the process answers. It does not touch the database, otherwise a database failure
    would make the application restart, which would solve nothing."""
    return JsonResponse({"status": "ok"})


@require_GET
def ready(request):
    """Readiness: the database answers and all the migrations are applied."""
    try:
        connection.ensure_connection()
        executor = MigrationExecutor(connection)
        missing = executor.migration_plan(executor.loader.graph.leaf_nodes())
    except OperationalError:
        return JsonResponse({"status": "database unreachable"}, status=503)
    if missing:
        return JsonResponse({"status": "migrations to apply", "how_many": len(missing)}, status=503)
    return JsonResponse({"status": "ready"})
