from django.urls import path
from . import views

app_name = 'managers'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('long-term/', views.long_term, name='long_term'),
    path('api/summary/', views.api_summary, name='api_summary'),
    path('api/sales_timeseries/', views.api_sales_timeseries, name='api_sales_timeseries'),
    path('api/status_counts/', views.api_status_counts, name='api_status_counts'),
    path('api/top_pizzas/', views.api_top_pizzas, name='api_top_pizzas'),
    path('api/top_categories/', views.api_top_categories, name='api_top_categories'),
    path('api/monthly/', views.api_monthly, name='api_monthly'),
    path('api/category_monthly/', views.api_category_monthly, name='api_category_monthly'),
    path('api/heatmap/', views.api_hourly_heatmap, name='api_hourly_heatmap'),
]
