from django.core.management import call_command


def test_there_are_no_model_changes_without_a_migration(db):
    call_command("makemigrations", "--check", "--dry-run")
