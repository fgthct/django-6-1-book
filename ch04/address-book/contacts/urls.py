from django.urls import path

from . import views

app_name = "contacts"

urlpatterns = [
    path("", views.contact_list, name="list"),
    path("new/", views.new, name="new"),
    path("count/", views.count, name="count"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/row/", views.row, name="row"),
    path("<int:pk>/edit/", views.edit, name="edit"),
    path("<int:pk>/delete/", views.delete, name="delete"),
]
