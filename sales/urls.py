from django.urls import path
from . import views

app_name = "sales"

urlpatterns = [
    path("", views.menu, name="menu"),
    path("add/", views.add_to_cart, name="add_to_cart"),
    path("cart/", views.view_cart, name="cart"),
    path("checkout/", views.checkout, name="checkout"),
    path("success/<int:order_id>/", views.checkout_success, name="success"),
]
