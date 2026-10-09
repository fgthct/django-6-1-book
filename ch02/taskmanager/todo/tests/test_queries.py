import pytest
from django.core.exceptions import FieldFetchBlocked
from django.db import connection, models
from django.test.utils import CaptureQueriesContext

from todo.models import Task


def count_queries(mode):
    with CaptureQueriesContext(connection) as context:
        names = [t.project.name for t in Task.objects.fetch_mode(mode)]
    return len(names), len(context)


def test_fetch_one_causes_the_n_plus_1_problem(tasks):
    rows, queries = count_queries(models.FETCH_ONE)
    assert rows == 12
    assert queries == 1 + 12


def test_fetch_peers_solves_it_with_two_queries(tasks):
    rows, queries = count_queries(models.FETCH_PEERS)
    assert rows == 12
    assert queries == 2


def test_fetch_raise_exposes_the_problem(tasks):
    with pytest.raises(FieldFetchBlocked):
        [t.project.name for t in Task.objects.fetch_mode(models.FETCH_RAISE)]


def test_fetch_raise_does_not_block_with_select_related(tasks):
    queryset = Task.objects.select_related("project")
    names = [t.project.name for t in queryset.fetch_mode(models.FETCH_RAISE)]
    assert len(names) == 12


def test_list_page_has_a_fixed_number_of_queries(client, tasks, django_assert_num_queries):
    with django_assert_num_queries(3):  # count, page, projects
        response = client.get("/")
    assert response.status_code == 200
