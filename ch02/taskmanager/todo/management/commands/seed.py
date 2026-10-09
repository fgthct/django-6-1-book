from datetime import date, timedelta

from django.core.management.base import BaseCommand

from todo.models import Project, Task


class Command(BaseCommand):
    help = "Create sample data: 3 projects and 30 tasks."

    def handle(self, *args, **options):
        today = date.today()
        projects = [
            Project.objects.get_or_create(name=name)[0]
            for name in ("Home", "Work", "Book")
        ]
        for i in range(30):
            Task.objects.create(
                project=projects[i % 3],
                title=f"Sample task {i + 1}",
                due_date=today + timedelta(days=i),
                completed=(i % 5 == 0),
            )
        self.stdout.write(self.style.SUCCESS("Sample data created."))
