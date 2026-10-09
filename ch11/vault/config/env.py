"""Reading the environment with clear errors: a value we don't understand stops the start."""

import os

from django.core.exceptions import ImproperlyConfigured

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def boolean(name, default):
    """`DEBUG=false` is a non-empty string, so "true" for Python: here it is really interpreted."""
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    key = value.strip().lower()
    if key in _TRUE:
        return True
    if key in _FALSE:
        return False
    raise ImproperlyConfigured(f"{name}={value!r} is not a boolean (use 1/0, true/false, yes/no, on/off).")


def integer(name, default):
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value.strip())
    except ValueError:
        raise ImproperlyConfigured(f"{name}={value!r} is not an integer.") from None


def comma_list(name, default=()):
    """`a, b,,c` becomes ["a", "b", "c"]: spaces and empty items are dropped."""
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return list(default)
    return [item.strip() for item in value.split(",") if item.strip()]


def required(name):
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        raise ImproperlyConfigured(f"{name} is missing: in production it is required.")
    return value
