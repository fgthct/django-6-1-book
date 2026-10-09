import multiprocessing
import os

bind = os.environ.get("BIND", "0.0.0.0:8000")
# A synchronous worker handles one request at a time: you need more workers than cores.
workers = int(os.environ.get("WEB_CONCURRENCY", multiprocessing.cpu_count() * 2 + 1))
timeout = 60
graceful_timeout = 30
worker_tmp_dir = "/dev/shm"  # noqa: S108 - the workers' heartbeat files in RAM, not on the container's disk
accesslog = "-"
errorlog = "-"
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(M)sms'
