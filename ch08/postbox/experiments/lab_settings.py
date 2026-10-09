from config.settings import *  # noqa

TASKS = {
    **TASKS,
    "immediate": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"},
}
