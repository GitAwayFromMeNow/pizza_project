from django.urls import path
from . import views

app_name = 'managers'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('api/summary/', views.api_summary, name='api_summary'),
    path('api/sales_timeseries/', views.api_sales_timeseries, name='api_sales_timeseries'),
    path('api/status_counts/', views.api_status_counts, name='api_status_counts'),
    path('api/top_pizzas/', views.api_top_pizzas, name='api_top_pizzas'),
    path('api/top_categories/', views.api_top_categories, name='api_top_categories'),
]
