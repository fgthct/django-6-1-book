"""The same task on both queues."""
import subprocess
import sys

import django

django.setup()
import redis  # noqa
from django.conf import settings  # noqa
from django.tasks import task_backends  # noqa

from experiments import demo_tasks  # noqa

redis.Redis.from_url(settings.REDIS_URL).flushall()
names = ["default", "redis"]
print(f"{'':34}{'PostgreSQL':14}{'Redis (RQ)':14}")
for feature in ("supports_defer", "supports_priority", "supports_get_result", "supports_async_task"):
    row = [str(getattr(task_backends[n], feature)) for n in names]
    print(f"{feature:34}{row[0]:14}{row[1]:14}")
print()
for n in names:
    r = demo_tasks.done.using(backend=n).enqueue()
    print(f"{n:8} right after enqueue: {r.status.name}")
    if n == "default":
        subprocess.run([sys.executable, "manage.py", "db_worker", "--batch"], capture_output=True, check=True)
    else:
        subprocess.run([sys.executable, "manage.py", "rqworker", "--job-class", "django_tasks_rq.Job", "--burst"], capture_output=True, check=True)
    r = demo_tasks.done.using(backend=n).get_result(r.id)
    print(f"{n:8} after the worker : {r.status.name}, return_value={r.return_value!r}")
