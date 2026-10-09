import time

from django.tasks import task


@task
def add(a, b):
    return a + b


@task(takes_context=True)
def fails(context):
    raise ValueError(f"attempt number {context.attempt}")


@task
def slow(seconds, marker):
    with open(marker, "a") as f:
        f.write(f"start {time.strftime('%H:%M:%S')}\n")
        f.flush()
        time.sleep(seconds)
        f.write(f"end {time.strftime('%H:%M:%S')}\n")
    return "done"


@task
def done():
    return "done"
