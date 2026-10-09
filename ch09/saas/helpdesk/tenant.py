"""The current tenant, for the duration of a request (or of a task, a command, a test)."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


class MissingTenant(Exception):
    """A tenant's data was touched without saying which tenant."""


@dataclass
class Context:
    organization: object | None = None


_context: ContextVar[Context | None] = ContextVar("tenant_context", default=None)


def current():
    context = _context.get()
    if context is None or context.organization is None:
        raise MissingTenant("no active tenant: use tenant(org) or go through the middleware")
    return context.organization


def current_or_none():
    context = _context.get()
    return None if context is None else context.organization


def activate(organization):
    """Choose the tenant inside an already open context (used by the API authentication)."""
    context = _context.get()
    if context is None:
        raise MissingTenant("no open context")
    context.organization = organization


@contextmanager
def tenant(organization=None):
    """Open a context, with or without a tenant. For middleware, tasks, commands and tests."""
    token = _context.set(Context(organization))
    try:
        yield _context.get()
    finally:
        _context.reset(token)
