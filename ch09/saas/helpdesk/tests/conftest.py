import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from helpdesk import keys, tenant
from helpdesk.models import Member, Organization, Ticket


@pytest.fixture(autouse=True)
def fast_passwords(settings):
    """The default password algorithm is deliberately slow: with six users per test the suite took
    49 seconds instead of 2. Tests don't need it."""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def fetch_raise(settings):
    """The design rule: in tests, a query that escapes us is an error, not a slowdown."""
    settings.FETCH_MODE = "FETCH_RAISE"


def make_org(slug, name, **kwargs):
    org = Organization.objects.create(slug=slug, name=name, **kwargs)
    User = get_user_model()
    members = {}
    for label, role in (("admin", Member.Role.ADMIN), ("agent", Member.Role.AGENT), ("reader", Member.Role.READER)):
        user = User.objects.create_user(username=f"{label}_{slug}", email=f"{label}@{slug}.test", password="pw")
        members[label] = Member.objects.create(user=user, organization=org, role=role)
    return org, members


@pytest.fixture
def acme(db):
    org, members = make_org("acme", "Acme Inc")
    org.members_by_label = members
    return org


@pytest.fixture
def rossi(db):
    org, members = make_org("rossi", "Rossi & Sons")
    org.members_by_label = members
    return org


@pytest.fixture
def admin_acme(acme):
    return acme.members_by_label["admin"]


@pytest.fixture
def agent_acme(acme):
    return acme.members_by_label["agent"]


@pytest.fixture
def reader_acme(acme):
    return acme.members_by_label["reader"]


@pytest.fixture
def admin_rossi(rossi):
    return rossi.members_by_label["admin"]


@pytest.fixture
def ticket_acme(acme):
    with tenant.tenant(acme):
        return Ticket.objects.create(title="Acme ticket", requester="c@acme.test")


@pytest.fixture
def ticket_rossi(rossi):
    with tenant.tenant(rossi):
        return Ticket.objects.create(title="Rossi ticket", requester="c@rossi.test")


class ApiClient:
    """A Django test client that speaks to the API with a key, on the organization's subdomain."""

    def __init__(self, org, member, host=None):
        self.key = keys.create_key(member)
        self.client = Client(HTTP_HOST=host or f"{org.slug}.localhost")

    def request(self, method, path, key=None, **kwargs):
        headers = {"Authorization": f"Bearer {key or self.key}"} if key != "" else {}
        return getattr(self.client, method)(f"/api/v1{path}", headers=headers, **kwargs)

    def get(self, path, data=None, **kw):
        return self.request("get", path, data=data, **kw)

    def post(self, path, data=None, **kw):
        return self.request("post", path, data=data, content_type="application/json", **kw)


def client_api(org, member, host=None):
    return ApiClient(org, member, host)


def client_web(org, member):
    client = Client(HTTP_HOST=f"{org.slug}.localhost")
    client.force_login(member.user)
    return client
