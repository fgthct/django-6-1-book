import io

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command

from documents.models import Document


@pytest.mark.django_db
def test_create_demo_creates_users_and_documents_and_can_run_twice(settings):
    settings.DEBUG = True  # the test runner turns DEBUG off: here we say "development"
    call_command("create_demo", stdout=io.StringIO())
    call_command("create_demo", stdout=io.StringIO())
    assert get_user_model().objects.count() == 4
    assert Document.objects.count() == 2
    assert get_user_model().objects.get(username="marta").check_password("password")


@pytest.mark.django_db
def test_create_demo_refuses_to_run_in_production(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError, match="DEBUG=1"):
        call_command("create_demo")
    assert get_user_model().objects.count() == 0
