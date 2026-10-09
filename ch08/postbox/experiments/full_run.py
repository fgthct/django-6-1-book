"""The complete test: two real workers, a real SMTP server, PostgreSQL and Redis.

A: 30 messages, limit 5 per second.
B: 6 messages, SMTP server OFF for the first 3 seconds.
C: 12 messages, slow SMTP server, both workers killed with kill -9.
"""
import collections
import os
import signal
import socket
import subprocess
import sys
import time
from datetime import timedelta

import django

django.setup()
import redis  # noqa
from aiosmtpd.controller import Controller  # noqa
from django.conf import settings  # noqa
from django.db import connection  # noqa
from django.utils import timezone  # noqa

from campaigns.models import Campaign, Contact, Delivery  # noqa
from campaigns.tasks import prepare_deliveries, requeue_lost  # noqa


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Collect:
    def __init__(self, delay=0.0):
        self.messages = []  # (time, recipient)
        self.delay = delay

    async def handle_DATA(self, server, session, envelope):
        self.messages.append((time.time(), envelope.rcpt_tos[0]))
        if self.delay:
            time.sleep(self.delay)  # deliberately blocking: one message at a time
        return "250 OK"


def reset():
    redis.Redis.from_url(settings.REDIS_URL).flushall()
    with connection.cursor() as c:
        c.execute("TRUNCATE django_tasks_database_dbtaskresult")
    Delivery.objects.all().delete()
    Campaign.objects.all().delete()
    Contact.objects.all().delete()


def make_campaign(n: int) -> Campaign:
    Contact.objects.bulk_create(
        [Contact(email=f"user{i}@example.com", name=f"User {i}") for i in range(1, n + 1)]
    )
    return Campaign.objects.create(subject="News", body="Hello {name}!")


def start_workers(env, n=2):
    return [
        subprocess.Popen(
            [sys.executable, "manage.py", "db_worker", "--no-reload", "--interval", "0.1"],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(n)
    ]


def stop(workers, sig=signal.SIGTERM):
    for w in workers:
        if w.poll() is None:
            w.send_signal(sig)
    for w in workers:
        w.wait()


def launch(campaign):
    campaign.status = Campaign.Status.SENDING
    campaign.started_at = timezone.now()
    campaign.save()
    prepare_deliveries.enqueue(campaign_id=campaign.pk)


def wait_completed(campaign, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        campaign.refresh_from_db()
        if campaign.status == Campaign.Status.COMPLETED:
            return time.time() - t0
        time.sleep(0.05)
    raise TimeoutError


def report(server, t0, campaign, elapsed=None):
    if elapsed is not None:
        print(f"  campaign completed in {elapsed:.1f} s")
    by_status = dict(collections.Counter(Delivery.objects.values_list("status", flat=True)))
    print(f"  deliveries by status: {by_status}")
    rcpts = [r for _, r in server.messages]
    print(f"  messages that reached the server: {len(rcpts)}, distinct recipients: {len(set(rcpts))}, "
          f"anyone more than once: {len(rcpts) != len(set(rcpts))}")
    attempts = collections.Counter(Delivery.objects.values_list("attempts", flat=True))
    print(f"  attempts per delivery: {dict(attempts)}")


def base_env(port, **extra):
    env = dict(os.environ, SMTP_PORT=str(port), **{k: str(v) for k, v in extra.items()})
    return env


# ---------------------------------------------------------------- A
reset()
print("== A: 30 messages, limit 5 per second")
server = Collect()
port = free_port()
ctrl = Controller(server, hostname="127.0.0.1", port=port)
ctrl.start()
workers = start_workers(base_env(port, CAMPAIGN_SENDS_PER_SECOND=5))
time.sleep(3)
campaign = make_campaign(30)
t0 = time.time()
launch(campaign)
elapsed = wait_completed(campaign)
stop(workers)
ctrl.stop()
report(server, t0, campaign, elapsed)
per_second = collections.Counter(int(t - t0) for t, _ in server.messages)
print(f"  messages arrived in each second: {dict(sorted(per_second.items()))}")

# ---------------------------------------------------------------- B
reset()
print("== B: SMTP server off for 3 seconds")
server = Collect()
port = free_port()
workers = start_workers(base_env(port, CAMPAIGN_SENDS_PER_SECOND=100, CAMPAIGN_BASE_WAIT=2))
time.sleep(3)
campaign = make_campaign(6)
t0 = time.time()
launch(campaign)
time.sleep(3)
ctrl = Controller(server, hostname="127.0.0.1", port=port)
ctrl.start()
print(f"  [{time.time() - t0:.1f} s] the SMTP server comes back on")
wait_completed(campaign)
elapsed = time.time() - t0
stop(workers)
ctrl.stop()
report(server, t0, campaign, elapsed)
per_second = collections.Counter(int(t - t0) for t, _ in server.messages)
print(f"  messages arrived in each second: {dict(sorted(per_second.items()))}")

# ---------------------------------------------------------------- C
reset()
print("== C: workers killed in the middle of a send")
server = Collect(delay=1.0)
port = free_port()
ctrl = Controller(server, hostname="127.0.0.1", port=port)
ctrl.start()
workers = start_workers(base_env(port, CAMPAIGN_SENDS_PER_SECOND=100))
time.sleep(3)
campaign = make_campaign(12)
t0 = time.time()
launch(campaign)
while len(server.messages) < 2:
    time.sleep(0.01)
stop(workers, signal.SIGKILL)
print(f"  [{time.time() - t0:.1f} s] both workers killed with kill -9; the server had already received "
      f"{len(server.messages)} messages")
time.sleep(1.5)  # let the server finish what it was doing
by_status = dict(collections.Counter(Delivery.objects.values_list("status", flat=True)))
print(f"  deliveries: {by_status}")
n = requeue_lost(timedelta(0))
print(f"  requeue_lost(): {n} deliveries put back in the queue")
server.delay = 0.0
workers = start_workers(base_env(port, CAMPAIGN_SENDS_PER_SECOND=100))
wait_completed(campaign)
stop(workers)
ctrl.stop()
print(f"  campaign completed; deliveries: {dict(collections.Counter(Delivery.objects.values_list('status', flat=True)))}")
rcpts = [r for _, r in server.messages]
print(f"  messages that reached the server: {len(rcpts)}, distinct recipients: {len(set(rcpts))}")
twice = sorted(r for r, c in collections.Counter(rcpts).items() if c > 1)
print(f"  recipients who received the message twice: {twice}")
reset()
