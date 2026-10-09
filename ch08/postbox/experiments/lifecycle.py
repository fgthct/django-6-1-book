"""Life cycle of a task: Immediate backend, PostgreSQL queue, a failing task."""
import subprocess
import sys

import django

django.setup()
from django.tasks import task_backends  # noqa

from experiments import demo_tasks  # noqa


def run_worker():
    subprocess.run(
        [sys.executable, "manage.py", "db_worker", "--batch"],
        check=True, capture_output=True,
    )


r = demo_tasks.add.using(backend="immediate").enqueue(2, 3)
print(f"Immediate : right after enqueue → {r.status.name}, return_value={r.return_value}")

r = demo_tasks.add.enqueue(2, 3)
print(f"PostgreSQL: right after enqueue → {r.status.name}")
run_worker()
r = demo_tasks.add.get_result(r.id)
print(f"            after the worker  → {r.status.name}, return_value={r.return_value}")

r = demo_tasks.fails.enqueue()
run_worker()
r = demo_tasks.fails.get_result(r.id)
last = r.errors[-1].traceback.strip().splitlines()[-1]
print(f"            failed task       → {r.status.name}, errors: {len(r.errors)}, last line: {last}")
print(f"            attempts made: {r.attempts} (no automatic retry)")
