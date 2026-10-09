from django.urls import path

from . import views

app_name = "todo"

urlpatterns = [
    path("", views.TaskListView.as_view(), name="list"),
    path("new/", views.TaskCreateView.as_view(), name="new"),
    path("<int:pk>/edit/", views.TaskUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.TaskDeleteView.as_view(), name="delete"),
    path("<int:pk>/toggle/", views.TaskToggleView.as_view(), name="toggle"),
]
