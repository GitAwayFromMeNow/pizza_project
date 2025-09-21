from __future__ import annotations
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _


class Pizza(models.Model):
    name = models.CharField(max_length=100, db_index=True)
    category = models.CharField(max_length=50, db_index=True)
    ingredients = models.TextField(blank=True)

    class Meta:
        unique_together = (
            ("name", "category"),
        )
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.category})"


class PizzaVariant(models.Model):
    class Size(models.TextChoices):
        S = "S", _("Small")
        M = "M", _("Medium")
        L = "L", _("Large")
        XL = "XL", _("XL")
        XXL = "XXL", _("XXL")

    pizza = models.ForeignKey(Pizza, on_delete=models.CASCADE, related_name="variants")
    size = models.CharField(max_length=3, choices=Size.choices, db_index=True)
    slug = models.SlugField(max_length=100, unique=True, help_text="pizza_name_id from CSV (e.g., hawaiian_m)")
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        unique_together = (
            ("pizza", "size"),
        )
        ordering = ["pizza__name", "size"]

    def __str__(self) -> str:
        return f"{self.pizza.name} [{self.size}]"


class Order(models.Model):
    external_id = models.IntegerField(unique=True, help_text="order_id from CSV")
    ordered_at = models.DateTimeField(db_index=True)

    def __str__(self) -> str:
        return f"Order #{self.external_id} @ {self.ordered_at:%Y-%m-%d %H:%M:%S}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(PizzaVariant, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    source_line_id = models.IntegerField(unique=True, help_text="pizza_id from CSV (unique line id)")

    class Meta:
        ordering = ["order__ordered_at", "id"]

    def __str__(self) -> str:
        return f"{self.quantity} x {self.variant} in {self.order}"

    @property
    def computed_total(self) -> Decimal:
        return (self.unit_price * Decimal(self.quantity)).quantize(Decimal("0.01"))
