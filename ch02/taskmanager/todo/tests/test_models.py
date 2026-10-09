from todo.models import Task


def test_str(projects):
    assert str(projects[0]) == "Home"


def test_default_ordering_is_deterministic(db):
    assert Task.objects.all().totally_ordered is True


def test_ordering_without_unique_field_is_not_deterministic(db):
    queryset = Task.objects.order_by("completed", "-created")
    assert queryset.totally_ordered is False


def test_adding_the_primary_key_makes_it_deterministic(db):
    queryset = Task.objects.order_by("completed", "-created", "pk")
    assert queryset.totally_ordered is True


def test_open_tasks_come_before_completed_ones(tasks):
    states = [t.completed for t in Task.objects.all()]
    assert states == sorted(states)
