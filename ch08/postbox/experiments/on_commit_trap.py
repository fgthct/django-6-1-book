"""Enqueue INSIDE a transaction, with a worker listening: PostgreSQL queue vs Redis queue."""
import subprocess
import sys
import time

import django

django.setup()
import redis  # noqa
from django.conf import settings  # noqa
from django.db import transaction  # noqa
from django.utils import timezone  # noqa

from campaigns.models import Campaign  # noqa
from campaigns.tasks import prepare_deliveries  # noqa

redis.Redis.from_url(settings.REDIS_URL).flushall()
workers = [
    subprocess.Popen([sys.executable, "manage.py", "db_worker", "--no-reload"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
    subprocess.Popen([sys.executable, "manage.py", "rqworker", "--job-class", "django_tasks_rq.Job"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
]
time.sleep(4)  # let the workers start
try:
    for backend in ("default", "redis"):
        task = prepare_deliveries.using(backend=backend)
        with transaction.atomic():
            c = Campaign.objects.create(subject="trap", body="x", status="sending", started_at=timezone.now())
            r = task.enqueue(campaign_id=c.pk)
            time.sleep(2)
            open_status = task.get_result(r.id).status.name
        time.sleep(2)
        after = task.get_result(r.id)
        line = f"{backend:8} with the transaction open: {open_status:10} after the commit: {after.status.name}"
        print(line)
        if after.errors:
            print("         error:", after.errors[-1].traceback.strip().splitlines()[-1])
finally:
    for w in workers:
        w.terminate()
        w.wait()
