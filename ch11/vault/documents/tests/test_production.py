"""The production configuration, tried in a separate process with a clean environment.

The test suite runs with the development settings, so it can't *see* what production does:
these tests start a new Python, with no variables of ours, and look at how it goes.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEY = "x7Fq-a-secret-key-that-is-long-enough-to-pass-the-deploy-checks-0123456789-abcdefghij"
PRODUCTION = {
    "SECRET_KEY": KEY,
    "ALLOWED_HOSTS": "vault.example.test",
    "SMTP_HOST": "mail.example.test",
    "TRUST_PROXY_SSL": "1",
    "DB_PASSWORD": os.environ.get("DB_PASSWORD", "vault"),
}
SCRIPT_SETTINGS = "import json; from django.conf import settings; print(json.dumps({'debug': settings.DEBUG}))"


def run(args, **environment):
    """Run Python in a clean process: none of the tests' variables, DEBUG absent (that is, production)."""
    env = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "")}
    env.update({k: v for k, v in os.environ.items() if k.startswith("DB_")})
    env.update(environment)
    return subprocess.run([sys.executable, *args], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)


def settings_of(**environment):
    return run(
        ["-c", f"import django; django.setup(); {SCRIPT_SETTINGS}"],
        DJANGO_SETTINGS_MODULE="config.settings",
        **environment,
    )


def test_without_a_secret_key_production_does_not_start():
    r = settings_of(ALLOWED_HOSTS="vault.example.test", SMTP_HOST="mail.example.test", DB_PASSWORD="x")
    assert r.returncode != 0 and "SECRET_KEY" in r.stderr


def test_without_a_mail_server_production_does_not_start():
    r = settings_of(**{k: v for k, v in PRODUCTION.items() if k != "SMTP_HOST"})
    assert r.returncode != 0 and "SMTP_HOST" in r.stderr


def test_without_allowed_hosts_production_does_not_start():
    r = settings_of(SECRET_KEY=KEY, SMTP_HOST="mail.example.test", DB_PASSWORD="x")
    assert r.returncode != 0 and "ALLOWED_HOSTS" in r.stderr


def test_without_a_database_password_production_does_not_start():
    r = settings_of(**{**PRODUCTION, "DB_PASSWORD": ""})
    assert r.returncode != 0 and "DB_PASSWORD" in r.stderr


def test_debug_false_is_really_false():
    # The classic mistake: bool("False") is True. Here "False" (and "off", "0", "no") turn DEBUG off.
    for value in ("False", "off", "0", "no"):
        r = settings_of(DEBUG=value, **PRODUCTION)
        assert r.returncode == 0 and json.loads(r.stdout) == {"debug": False}, value


def test_an_incomprehensible_debug_value_stops_the_start():
    r = settings_of(DEBUG="maybe", **PRODUCTION)
    assert r.returncode != 0 and "DEBUG" in r.stderr


def test_in_development_it_is_enough_to_say_debug():
    r = settings_of(DEBUG="1", DB_PASSWORD="x")
    assert r.returncode == 0 and json.loads(r.stdout) == {"debug": True}


def test_in_production_the_mail_goes_through_smtp():
    script = (
        "import django; django.setup(); from django.conf import settings; print(settings.MAILERS['default']['BACKEND'])"
    )
    r = run(["-c", script], DJANGO_SETTINGS_MODULE="config.settings", **PRODUCTION)
    assert r.returncode == 0 and r.stdout.strip() == "django.core.mail.backends.smtp.EmailBackend"


def test_check_deploy_finds_nothing_to_report():
    r = run(["manage.py", "check", "--deploy", "--fail-level", "WARNING"], **PRODUCTION)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "no issues" in r.stdout


def test_check_deploy_notices_when_the_redirect_to_https_is_removed():
    r = run(["manage.py", "check", "--deploy", "--fail-level", "WARNING"], SECURE_SSL_REDIRECT="0", **PRODUCTION)
    assert r.returncode != 0 and "SECURE_SSL_REDIRECT" in (r.stdout + r.stderr)


def test_check_deploy_rejects_a_console_mailer():
    # mail.E001 (Django 6.1): a development-only mail backend in production is an error.
    script = (
        "import django; from django.conf import settings; "
        "from django.core.management import call_command; "
        "settings.MAILERS['default']['BACKEND'] = 'django.core.mail.backends.console.EmailBackend'; "
        "django.setup(); call_command('check', deploy=True)"
    )
    r = run(["-c", script], DJANGO_SETTINGS_MODULE="config.settings", **PRODUCTION)
    assert r.returncode != 0 and "mail.E001" in (r.stdout + r.stderr)


# --- HTTPS behind the proxy ----------------------------------------------------------------

SCRIPT_HTTP = """
import json, django
django.setup()
from django.test import Client
c = Client(HTTP_HOST="vault.example.test")
proxy = {"HTTP_X_FORWARDED_PROTO": "https"}
page_http = c.get("/login/")
health_https = c.get("/health/", **proxy)
print(json.dumps({
    "health_http": c.get("/health/").status_code,
    "page_http": [page_http.status_code, page_http.headers.get("Location", "")],
    "health_https": [health_https.status_code, "Strict-Transport-Security" in health_https.headers],
    "page_https": c.get("/", **proxy).status_code,
    "secure_cookies": [__import__("django.conf").conf.settings.SESSION_COOKIE_SECURE,
                       __import__("django.conf").conf.settings.CSRF_COOKIE_SECURE],
}))
"""


def responses(**environment):
    r = run(["-c", SCRIPT_HTTP], DJANGO_SETTINGS_MODULE="config.settings", **{**PRODUCTION, **environment})
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_behind_the_proxy_http_is_sent_to_https_and_the_header_is_trusted():
    result = responses()
    assert result["health_http"] == 200
    assert result["page_http"][0] == 301 and result["page_http"][1].startswith("https://")
    assert result["health_https"] == [200, True]  # HSTS is present when the request is secure
    assert result["page_https"] == 302  # no redirect to HTTPS: it reaches the login
    assert result["secure_cookies"] == [True, True]


def test_without_trust_in_the_proxy_the_header_sent_by_the_client_does_not_count():
    result = responses(TRUST_PROXY_SSL="0")
    assert result["page_https"] == 301  # any client could declare itself "already on HTTPS"


# --- Static files ----------------------------------------------------------------------------

SCRIPT_STATIC = """
import json, django
django.setup()
from django.test import Client
c = Client(HTTP_HOST="vault.example.test")
manifest = json.load(open(__import__("django.conf").conf.settings.STATIC_ROOT / "staticfiles.json"))
name = manifest["paths"]["app.css"]
r = c.get("/static/" + name, HTTP_X_FORWARDED_PROTO="https")
print(json.dumps({"name": name, "status": r.status_code, "cache": r.headers.get("Cache-Control", ""),
                  "gzip": (__import__("django.conf").conf.settings.STATIC_ROOT / (name + ".gz")).exists()}))
"""


def test_in_production_the_application_serves_the_static_files_with_a_long_cache(tmp_path):
    environment = {**PRODUCTION, "STATIC_ROOT": str(tmp_path / "static")}
    collected = run(["manage.py", "collectstatic", "--noinput"], **environment)
    assert collected.returncode == 0, collected.stderr
    r = run(["-c", SCRIPT_STATIC], DJANGO_SETTINGS_MODULE="config.settings", **environment)
    assert r.returncode == 0, r.stderr
    result = json.loads(r.stdout)
    assert result["name"] != "app.css" and result["name"].startswith("app.") and result["name"].endswith(".css")
    assert result["status"] == 200 and "immutable" in result["cache"] and result["gzip"] is True
