from django.urls import path
from . import views

app_name = 'kitchen'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('api/orders/', views.api_open_orders, name='api_open_orders'),
    path('api/orders/<int:order_id>/send/', views.api_send_for_delivery, name='api_send_for_delivery'),
]
