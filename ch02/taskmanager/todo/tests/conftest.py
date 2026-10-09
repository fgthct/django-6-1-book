import pytest

from todo.models import Project, Task


@pytest.fixture
def projects(db):
    return [Project.objects.create(name=name) for name in ("Home", "Work", "Book")]


@pytest.fixture
def tasks(projects):
    return [
        Task.objects.create(
            project=projects[i % 3],
            title=f"Task {i + 1}",
            completed=(i % 4 == 0),
        )
        for i in range(12)
    ]
