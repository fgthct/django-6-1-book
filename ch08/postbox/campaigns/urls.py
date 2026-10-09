from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("campaigns/new/", views.create, name="create"),
    path("campaigns/<int:pk>/", views.detail, name="detail"),
    path("campaigns/<int:pk>/start/", views.start, name="start"),
    path("campaigns/<int:pk>/progress/", views.progress, name="progress"),
]
