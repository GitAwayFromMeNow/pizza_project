from __future__ import annotations
from decimal import Decimal
from typing import Dict

from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone

from .models import Pizza, PizzaVariant, Order, OrderItem


# --- Cart utilities (session-based) ---
CART_SESSION_KEY = "cart"


def _get_cart(session) -> Dict[str, int]:
    cart = session.get(CART_SESSION_KEY)
    if not isinstance(cart, dict):
        cart = {}
    return cart


def _save_cart(session, cart: Dict[str, int]) -> None:
    # Clean zero or negative quantities
    clean = {k: v for k, v in cart.items() if v > 0}
    session[CART_SESSION_KEY] = clean
    session.modified = True


# --- Views ---

def menu(request: HttpRequest) -> HttpResponse:
    pizzas = Pizza.objects.order_by("name").prefetch_related("variants")
    return render(request, "sales/menu.html", {"pizzas": pizzas})


def add_to_cart(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")
    try:
        variant_id = int(request.POST.get("variant_id", "0"))
        qty = int(request.POST.get("quantity", "1"))
    except ValueError:
        return HttpResponseBadRequest("Invalid input")
    variant = get_object_or_404(PizzaVariant, id=variant_id)
    if qty < 1:
        qty = 1
    cart = _get_cart(request.session)
    cart[str(variant.id)] = cart.get(str(variant.id), 0) + qty
    _save_cart(request.session, cart)
    messages.success(request, f"Added {qty} x {variant} to cart.")
    return redirect("sales:cart")


def view_cart(request: HttpRequest) -> HttpResponse:
    cart = _get_cart(request.session)
    variant_ids = [int(k) for k in cart.keys()]
    variants = {v.id: v for v in PizzaVariant.objects.filter(id__in=variant_ids).select_related("pizza")}

    items = []
    subtotal = Decimal("0.00")
    for key, qty in cart.items():
        vid = int(key)
        variant = variants.get(vid)
        if not variant:
            continue
        unit = variant.unit_price
        total = (unit * Decimal(qty)).quantize(Decimal("0.01"))
        subtotal += total
        items.append({
            "variant": variant,
            "quantity": qty,
            "unit_price": unit,
            "total_price": total,
        })

    if request.method == "POST":
        # Update quantities
        new_cart: Dict[str, int] = {}
        for item in items:
            field = f"qty_{item['variant'].id}"
            try:
                new_qty = int(request.POST.get(field, item["quantity"]))
            except (TypeError, ValueError):
                new_qty = item["quantity"]
            new_cart[str(item['variant'].id)] = max(0, new_qty)
        _save_cart(request.session, new_cart)
        messages.success(request, "Cart updated.")
        return redirect("sales:cart")

    return render(request, "sales/cart.html", {
        "items": items,
        "subtotal": subtotal,
    })


def _generate_external_id() -> int:
    # Use a high range based on timestamp to avoid collision with CSV order ids
    ts = int(timezone.now().timestamp())
    return 1_000_000_000 + ts


@transaction.atomic
def checkout(request: HttpRequest) -> HttpResponse:
    cart = _get_cart(request.session)
    if not cart:
        messages.warning(request, "Your cart is empty.")
        return redirect("sales:menu")

    variant_ids = [int(k) for k in cart.keys()]
    variants = {v.id: v for v in PizzaVariant.objects.filter(id__in=variant_ids).select_related("pizza")}

    # Compute totals and validate
    order_items_data = []
    subtotal = Decimal("0.00")
    for sid, qty in cart.items():
        vid = int(sid)
        variant = variants.get(vid)
        if not variant or qty <= 0:
            continue
        unit = variant.unit_price
        total = (unit * Decimal(qty)).quantize(Decimal("0.01"))
        subtotal += total
        order_items_data.append((variant, qty, unit, total))

    if not order_items_data:
        messages.warning(request, "Your cart is empty.")
        return redirect("sales:menu")

    # Prepare initial form data (persist values between POST/GET)
    form_data = {
        "first_name": request.POST.get("first_name", ""),
        "last_name": request.POST.get("last_name", ""),
        "phone": request.POST.get("phone", ""),
        "street": request.POST.get("street", ""),
        "city": request.POST.get("city", ""),
        "zip_code": request.POST.get("zip", ""),
    }

    if request.method == "POST":
        # Basic validation (require all fields)
        errors = {}
        if not form_data["first_name"].strip():
            errors["first_name"] = "First name is required."
        if not form_data["last_name"].strip():
            errors["last_name"] = "Last name is required."
        if not form_data["phone"].strip():
            errors["phone"] = "Phone number is required."
        if not form_data["street"].strip():
            errors["street"] = "Street is required."
        if not form_data["city"].strip():
            errors["city"] = "City is required."
        if not form_data["zip_code"].strip():
            errors["zip_code"] = "ZIP is required."

        if errors:
            for msg in errors.values():
                messages.error(request, msg)
        else:
            # Create Order and OrderItems
            # Ensure unique external_id (retry on rare collision)
            for _ in range(3):
                ext_id = _generate_external_id()
                if not Order.objects.filter(external_id=ext_id).exists():
                    break
            else:
                messages.error(request, "Unable to create order. Please try again.")
                return redirect("sales:cart")

            order = Order.objects.create(
                external_id=ext_id,
                ordered_at=timezone.now(),
                customer_first_name=form_data["first_name"].strip(),
                customer_last_name=form_data["last_name"].strip(),
                phone=form_data["phone"].strip(),
                street=form_data["street"].strip(),
                city=form_data["city"].strip(),
                zip_code=form_data["zip_code"].strip(),
            )
            for (variant, qty, unit, total) in order_items_data:
                OrderItem.objects.create(
                    order=order,
                    variant=variant,
                    quantity=qty,
                    unit_price=unit,
                    total_price=total,
                    source_line_id=None,
                )
            # Clear cart
            _save_cart(request.session, {})
            return redirect("sales:success", order_id=order.id)

    return render(request, "sales/checkout.html", {
        "items": order_items_data,
        "subtotal": subtotal,
        "form": form_data,
    })


def checkout_success(request: HttpRequest, order_id: int) -> HttpResponse:
    order = get_object_or_404(Order.objects.prefetch_related("items__variant__pizza"), id=order_id)
    return render(request, "sales/checkout_success.html", {"order": order})
