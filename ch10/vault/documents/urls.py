from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.document_list, name="list"),
    path("login/", auth_views.LoginView.as_view(template_name="documents/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("new/", views.create, name="create"),
    path("search/", views.search_view, name="search"),
    path("documents/<uuid:pk>/", views.detail, name="detail"),
    path("documents/<uuid:pk>/version/", views.new_version, name="new_version"),
    path("documents/<uuid:pk>/review/", views.send_for_review, name="send_for_review"),
    path("documents/<uuid:pk>/decide/", views.decide, name="decide"),
    path("documents/<uuid:pk>/cancel/", views.cancel_review, name="cancel_review"),
    path("documents/<uuid:pk>/access/", views.grant_access, name="grant_access"),
    path("documents/<uuid:pk>/access/<int:user_id>/revoke/", views.revoke_access, name="revoke_access"),
    path("documents/<uuid:pk>/download/<int:number>/", views.download, name="download"),
]
