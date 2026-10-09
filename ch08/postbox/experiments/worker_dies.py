"""What happens if the worker is killed with kill -9 in the middle of a task?"""
import os
import signal
import subprocess
import sys
import tempfile
import time

import django

django.setup()
from experiments import demo_tasks  # noqa

marker = os.path.join(tempfile.mkdtemp(), "task.log")
worker = subprocess.Popen([sys.executable, "manage.py", "db_worker", "--no-reload"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(3)
r = demo_tasks.slow.enqueue(6, marker)
time.sleep(2)
print("after 2 s of work       :", demo_tasks.slow.get_result(r.id).status.name)
os.kill(worker.pid, signal.SIGKILL)
worker.wait()
print("worker killed with -9   :", demo_tasks.slow.get_result(r.id).status.name)
new = subprocess.Popen([sys.executable, "manage.py", "db_worker", "--no-reload"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(10)
print("10 s after the new worker:", demo_tasks.slow.get_result(r.id).status.name)
new.terminate(); new.wait()
print("task log:")
print(open(marker).read().rstrip())
