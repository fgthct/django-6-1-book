import pytest

from contacts.models import Contact

CITIES = ["Boston", "Chicago", "Denver", "Austin", "Seattle", "Miami", "Portland"]


@pytest.fixture
def contacts(db):
    return [
        Contact.objects.create(
            name=f"Person {i:02d}",
            email=f"person{i:02d}@example.com",
            city=CITIES[i % len(CITIES)],
        )
        for i in range(25)
    ]
