import warnings

import django

django.setup()
from django.core import mail  # noqa
from django.core.mail import send_mail  # noqa

for alias in ("default", "campaigns"):
    m = mail.mailers[alias]
    print(f"mailers[{alias!r}] → {type(m).__module__}.{type(m).__name__} { {'host': m.host, 'port': m.port} if hasattr(m, 'host') else {} }")

import io, contextlib  # noqa
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    send_mail("Hi", "Body", "a@x.example", ["b@x.example"], using="default")
print("send_mail(..., using='default')  → the message goes out on the terminal (omitted here)")

print("a mailer that doesn't exist:")
try:
    send_mail("Hi", "Body", "a@x.example", ["b@x.example"], using="marketing")
except Exception as e:
    print(f"  {type(e).__name__}: {e}")

print("old and new don't mix:")
try:
    send_mail("Hi", "Body", "a@x.example", ["b@x.example"], using="default", fail_silently=True)
except Exception as e:
    print(f"  {type(e).__name__}: {e}")
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    mail.get_connection()
for x in w:
    print(f"  {x.category.__name__}: {x.message}")
