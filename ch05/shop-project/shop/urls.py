from django.urls import path

from . import views

app_name = "shop"

urlpatterns = [
    path("", views.catalog, name="catalog"),
    path("cart/", views.cart, name="cart"),
    path("cart/add/<int:pk>/", views.add, name="add"),
    path("cart/set/<int:pk>/", views.set_quantity, name="set_quantity"),
    path("order/", views.place_order, name="place_order"),
    path("thanks/<int:pk>/", views.thanks, name="thanks"),
]
