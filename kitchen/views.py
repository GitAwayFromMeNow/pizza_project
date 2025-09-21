from __future__ import annotations
from datetime import date
from typing import List, Dict

from django.http import JsonResponse, HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone
from django.db.models import Prefetch
from django.contrib.auth.decorators import login_required

from sales.models import Order, OrderItem


@require_GET
@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    return render(request, 'kitchen/dashboard.html')


@require_GET
@login_required
def api_open_orders(request: HttpRequest) -> JsonResponse:
    # Show today's orders that are not out for delivery or delivered
    today = timezone.localdate()
    qs = (
        Order.objects
        .filter(ordered_at__date=today)
        .exclude(status__in=[Order.Status.OUT_FOR_DELIVERY, Order.Status.DELIVERED])
        .order_by('-ordered_at')
        .prefetch_related(Prefetch('items', queryset=OrderItem.objects.select_related('variant__pizza')))
    )
    data: List[Dict] = []
    for o in qs:
        items = []
        for it in o.items.all():
            items.append({
                'id': it.id,
                'qty': it.quantity,
                'pizza': it.variant.pizza.name,
                'size': it.variant.get_size_display(),
            })
        data.append({
            'id': o.id,
            'external_id': o.external_id,
            'ordered_at': timezone.localtime(o.ordered_at).strftime('%H:%M:%S'),
            'status': o.status,
            'customer': {
                'name': f"{o.customer_first_name or ''} {o.customer_last_name or ''}".strip(),
                'phone': o.phone or '',
                'address': ", ".join([p for p in [o.street, o.city] if p]) + (f" {o.zip_code}" if o.zip_code else ''),
            },
            'items': items,
        })
    return JsonResponse({'orders': data})


@require_POST
@login_required
def api_send_for_delivery(request: HttpRequest, order_id: int) -> JsonResponse:
    order = get_object_or_404(Order, id=order_id)
    # Move to out_for_delivery if not already delivered
    if order.status not in (Order.Status.OUT_FOR_DELIVERY, Order.Status.DELIVERED):
        order.status = Order.Status.OUT_FOR_DELIVERY
        order.out_for_delivery_at = timezone.now()
        order.save(update_fields=['status', 'out_for_delivery_at'])
    return JsonResponse({'ok': True, 'order_id': order.id, 'status': order.status})
