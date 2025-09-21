from __future__ import annotations
from datetime import timedelta
from typing import List, Dict

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, F
from django.db.models.functions import TruncDate, TruncMonth, ExtractHour, ExtractWeekDay
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from sales.models import Order, OrderItem


@require_GET
@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    return render(request, 'managers/dashboard.html')


@require_GET
@login_required
def api_summary(request: HttpRequest) -> JsonResponse:
    now = timezone.localtime()
    today = timezone.localdate()
    start_7 = now - timedelta(days=7)

    # Revenue totals
    total_revenue = OrderItem.objects.aggregate(total=Sum('total_price'))['total'] or 0

    # Today
    today_orders = Order.objects.filter(ordered_at__date=today)
    today_order_count = today_orders.count()
    today_revenue = OrderItem.objects.filter(order__ordered_at__date=today).aggregate(total=Sum('total_price'))['total'] or 0

    # Last 7 days revenue
    last7_revenue = (
        OrderItem.objects
        .filter(order__ordered_at__gte=start_7)
        .aggregate(total=Sum('total_price'))['total'] or 0
    )

    # Average order value (last 30 days)
    start_30 = now - timedelta(days=30)
    q = (
        Order.objects
        .filter(ordered_at__gte=start_30)
        .annotate(order_total=Sum('items__total_price'))
    )
    count30 = q.count() or 1
    sum30 = sum([o.order_total or 0 for o in q])
    avg_order_value = (sum30 / count30) if count30 else 0

    return JsonResponse({
        'today_order_count': today_order_count,
        'today_revenue': float(today_revenue),
        'last7_revenue': float(last7_revenue),
        'avg_order_value_30d': float(avg_order_value),
        'total_revenue_all_time': float(total_revenue),
    })


@require_GET
@login_required
def api_sales_timeseries(request: HttpRequest) -> JsonResponse:
    now = timezone.localtime()
    start = now - timedelta(days=29)
    # Aggregate revenue per day last 30 days
    qs = (
        OrderItem.objects
        .filter(order__ordered_at__date__gte=start.date())
        .annotate(day=TruncDate('order__ordered_at'))
        .values('day')
        .annotate(revenue=Sum('total_price'), orders=Count('order', distinct=True))
        .order_by('day')
    )
    points = []
    # Ensure all days present
    day = start.date()
    today = timezone.localdate()
    data_map = {row['day']: row for row in qs}
    while day <= today:
        row = data_map.get(day)
        points.append({
            'day': day.isoformat(),
            'revenue': float(row['revenue']) if row else 0.0,
            'orders': int(row['orders']) if row else 0,
        })
        day += timedelta(days=1)
    return JsonResponse({'points': points})


@require_GET
@login_required
def api_status_counts(request: HttpRequest) -> JsonResponse:
    # Distribution of order statuses (today)
    today = timezone.localdate()
    qs = (
        Order.objects
        .filter(ordered_at__date=today)
        .values('status')
        .annotate(n=Count('id'))
    )
    return JsonResponse({'counts': list(qs)})


@require_GET
@login_required
def api_top_pizzas(request: HttpRequest) -> JsonResponse:
    # Top pizzas by revenue over last 30 days
    start = timezone.localtime() - timedelta(days=30)
    qs = (
        OrderItem.objects
        .filter(order__ordered_at__gte=start)
        .values(name=F('variant__pizza__name'))
        .annotate(quantity=Sum('quantity'), revenue=Sum('total_price'))
        .order_by('-revenue')[:10]
    )
    out = [{'name': row['name'], 'quantity': int(row['quantity'] or 0), 'revenue': float(row['revenue'] or 0)} for row in qs]
    return JsonResponse({'top': out})


@require_GET
@login_required
def api_top_categories(request: HttpRequest) -> JsonResponse:
    # Top categories by revenue over last 30 days
    start = timezone.localtime() - timedelta(days=30)
    qs = (
        OrderItem.objects
        .filter(order__ordered_at__gte=start)
        .values(category=F('variant__pizza__category'))
        .annotate(quantity=Sum('quantity'), revenue=Sum('total_price'))
        .order_by('-revenue')
    )
    out = [{'category': row['category'], 'quantity': int(row['quantity'] or 0), 'revenue': float(row['revenue'] or 0)} for row in qs]
    return JsonResponse({'top': out})


@require_GET
@login_required
def long_term(request: HttpRequest) -> HttpResponse:
    return render(request, 'managers/long_term.html')


@require_GET
@login_required
def api_monthly(request: HttpRequest) -> JsonResponse:
    # Monthly revenue and orders across entire dataset
    qs = (
        OrderItem.objects
        .annotate(month=TruncMonth('order__ordered_at'))
        .values('month')
        .annotate(revenue=Sum('total_price'), orders=Count('order', distinct=True))
        .order_by('month')
    )
    out = [
        {
            'month': row['month'].date().isoformat(),
            'revenue': float(row['revenue'] or 0),
            'orders': int(row['orders'] or 0),
        }
        for row in qs
    ]
    return JsonResponse({'points': out})


@require_GET
@login_required
def api_category_monthly(request: HttpRequest) -> JsonResponse:
    # Monthly revenue by category for all time
    qs = (
        OrderItem.objects
        .annotate(month=TruncMonth('order__ordered_at'))
        .values('month', category=F('variant__pizza__category'))
        .annotate(revenue=Sum('total_price'))
        .order_by('month', 'category')
    )
    out = [
        {
            'month': row['month'].date().isoformat(),
            'category': row['category'],
            'revenue': float(row['revenue'] or 0),
        }
        for row in qs
    ]
    return JsonResponse({'rows': out})


@require_GET
@login_required
def api_hourly_heatmap(request: HttpRequest) -> JsonResponse:
    # Heatmap: orders by weekday (1=Sun..7=Sat in Django) and hour (0-23) across all data
    qs = (
        OrderItem.objects
        .annotate(wd=ExtractWeekDay('order__ordered_at'), hr=ExtractHour('order__ordered_at'))
        .values('wd', 'hr')
        .annotate(orders=Count('order', distinct=True), revenue=Sum('total_price'))
        .order_by('wd', 'hr')
    )
    rows = [
        {
            'weekday': int(row['wd'] or 0),
            'hour': int(row['hr'] or 0),
            'orders': int(row['orders'] or 0),
            'revenue': float(row['revenue'] or 0),
        }
        for row in qs
    ]
    # Provide labels mapping starting Sunday
    labels = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']
    return JsonResponse({'rows': rows, 'weekday_labels': labels})
