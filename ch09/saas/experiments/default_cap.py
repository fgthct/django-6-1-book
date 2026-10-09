import os, sys
import django
django.setup()
from django.test import Client
token = open("/tmp/token9").read().strip()
for host in ("acme.localhost",):
    r = Client(HTTP_HOST=host).get("/api/v1/tickets", {"limit": 1000}, headers={"Authorization": f"Bearer {token}"})
    print(os.environ["DJANGO_SETTINGS_MODULE"], "limit=1000 →", r.status_code)
