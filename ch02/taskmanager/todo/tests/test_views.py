from django.urls import reverse

from todo.models import Task


def test_list_shows_the_tasks(client, tasks):
    response = client.get(reverse("todo:list"))
    assert response.status_code == 200
    assert "Task 2" in response.content.decode()


def test_list_is_paginated(client, tasks):
    response = client.get(reverse("todo:list"))
    assert len(response.context["object_list"]) == 10
    assert response.context["is_paginated"] is True


def test_open_filter(client, tasks):
    response = client.get(reverse("todo:list"), {"status": "open"})
    assert all(not t.completed for t in response.context["object_list"])


def test_completed_filter(client, tasks):
    response = client.get(reverse("todo:list"), {"status": "completed"})
    assert response.context["object_list"]
    assert all(t.completed for t in response.context["object_list"])


def test_create(client, projects):
    data = {"project": projects[0].pk, "title": "Write the chapter", "description": ""}
    response = client.post(reverse("todo:new"), data)
    assert response.status_code == 302
    assert Task.objects.filter(title="Write the chapter").exists()


def test_create_without_a_title_shows_the_error(client, projects):
    response = client.post(reverse("todo:new"), {"project": projects[0].pk, "title": ""})
    assert response.status_code == 200
    assert Task.objects.count() == 0


def test_edit(client, tasks):
    t = tasks[1]
    data = {"project": t.project_id, "title": "New title", "description": ""}
    client.post(reverse("todo:edit", args=[t.pk]), data)
    t.refresh_from_db()
    assert t.title == "New title"


def test_toggle_flips_the_state(client, tasks):
    t = tasks[1]
    assert t.completed is False
    client.post(reverse("todo:toggle", args=[t.pk]))
    t.refresh_from_db()
    assert t.completed is True


def test_toggle_rejects_get(client, tasks):
    response = client.get(reverse("todo:toggle", args=[tasks[0].pk]))
    assert response.status_code == 405


def test_delete(client, tasks):
    t = tasks[0]
    client.post(reverse("todo:delete", args=[t.pk]))
    assert not Task.objects.filter(pk=t.pk).exists()


def test_admin_task_list(admin_client, tasks):
    response = admin_client.get("/admin/todo/task/")
    assert response.status_code == 200
