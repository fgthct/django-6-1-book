from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .api import api

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", auth_views.LoginView.as_view(template_name="helpdesk/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("counters/", views.counters, name="counters"),
    path("tickets/<uuid:pk>/", views.ticket_detail, name="ticket"),
    path("tickets/<uuid:pk>/status/", views.change_status, name="change_status"),
    path("tickets/<uuid:pk>/comments/", views.add_comment, name="add_comment"),
    path("csp-report/", views.csp_report, name="csp_report"),
    path("api/v1/", api.urls),
]
