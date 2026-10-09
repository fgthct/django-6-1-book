"""Runs one small probe for each feature that changes between Django 5.2, 6.0 and 6.1."""
import os
import warnings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lab.settings")
import django

django.setup()

from django.core.management import call_command  # noqa: E402
from django.db import connection  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

call_command("migrate", verbosity=0, run_syncdb=True)

from demo.models import Note  # noqa: E402


def probe_admins_as_tuples():
    from django.core import mail
    from django.test.utils import override_settings

    with override_settings(ADMINS=[("Ann", "ann@example.com")]):
        mail.mail_admins("subject", "message")
    return "ok"


def probe_bad_header_error():
    from django.core.mail import BadHeaderError  # noqa: F401

    return "ok"


def probe_checkconstraint_check():
    from django.db.models import CheckConstraint, Q

    CheckConstraint(check=Q(text__gt=""), name="text_not_empty")
    return "ok"


def probe_double_dot_in_templates():
    from django.template import Context, Template

    Template("{{ a..b }}").render(Context({"a": {}}))
    return "ok"


def probe_email_positional_args():
    from django.core.mail import EmailMessage

    EmailMessage("s", "b", "a@example.com", ["b@example.com"], ["c@example.com"])
    return "ok"


def probe_fail_silently():
    from django.core.mail import send_mail

    send_mail("s", "b", "a@example.com", ["b@example.com"], fail_silently=True)
    return "ok"


def probe_empty_file_is_truthy():
    from django.core.files import File

    return "ok (bool(File(None)) = %s)" % bool(File(None))


def probe_first_without_ordering():
    with CaptureQueriesContext(connection) as q:
        Note.objects.order_by().first()
    return "ok (ORDER BY present)" if "ORDER BY" in q[0]["sql"] else "ok (no ORDER BY)"


def probe_format_html_without_args():
    from django.utils.html import format_html

    format_html("<b>x</b>")
    return "ok"


def probe_get_connection():
    from django.core.mail import get_connection

    get_connection()
    return "ok"


def probe_is_iterable():
    from django.utils.itercompat import is_iterable

    is_iterable([1])
    return "ok"


def probe_pbkdf2_iterations():
    from django.contrib.auth.hashers import make_password

    return "ok (iterations = %s)" % make_password("x").split("$")[1]


def probe_json_none():
    Note.objects.create(text="a", data={"k": None})
    return "ok (%d match)" % Note.objects.filter(data__k__iexact=None).count()


def probe_orphans():
    from django.core.paginator import Paginator

    Paginator(list(range(10)), 5, orphans=5)
    return "ok"


def probe_register_converter_twice():
    from django.urls import register_converter

    class Conv:
        regex = "[0-9]+"

        def to_python(self, value):
            return int(value)

        def to_url(self, value):
            return str(value)

    register_converter(Conv, "number")
    register_converter(Conv, "number")
    return "ok"


def probe_positional_save():
    Note(text="p").save(False, False)
    return "ok"


def probe_savepoint():
    from django.db import transaction

    with transaction.atomic():
        sid = transaction.savepoint()
        transaction.savepoint_commit(sid)
    return "ok"


def probe_select_related_without_args():
    list(Note.objects.select_related())
    return "ok"


def probe_urlize():
    from django.utils.html import urlize

    return "ok (%s)" % ("linked" if "<a " in urlize("write to www.example.com now") else "not linked")


def probe_values_list_flat_without_field():
    list(Note.objects.values_list(flat=True))
    return "ok"


def run(name, fn):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            result = fn()
        except Exception as e:  # noqa: BLE001
            return "ERROR %s: %s" % (type(e).__name__, str(e).splitlines()[0])
    tags = sorted({w.category.__name__ for w in caught if w.category.__name__.startswith("RemovedInDjango")})
    return result + ("  [%s]" % ", ".join(tags) if tags else "")


if __name__ == "__main__":
    print("Django", django.get_version())
    for name, fn in sorted((n[6:], f) for n, f in globals().items() if n.startswith("probe_")):
        print("%-42s %s" % (name, run(name, fn)))
