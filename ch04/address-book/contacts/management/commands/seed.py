from django.core.management.base import BaseCommand

from contacts.models import Contact

CITIES = ["Boston", "Chicago", "Denver", "Austin", "Seattle", "Miami", "Portland"]


class Command(BaseCommand):
    help = "Create 35 sample contacts."

    def handle(self, *args, **options):
        created = 0
        for i in range(35):
            _, was_created = Contact.objects.get_or_create(
                email=f"person{i:02d}@example.com",
                defaults={
                    "name": f"Person {i:02d}",
                    "phone": f"555-01{i:02d}",
                    "city": CITIES[i % len(CITIES)],
                },
            )
            created += was_created
        total = Contact.objects.count()
        self.stdout.write(f"{created} contacts created, {total} in total.")
