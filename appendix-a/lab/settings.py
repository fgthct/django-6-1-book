SECRET_KEY = "only-for-the-lab"
DEBUG = True
INSTALLED_APPS = ["demo"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "OPTIONS": {}}]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
USE_TZ = True
# DEFAULT_AUTO_FIELD is deliberately NOT set: this is the "old project" case.
