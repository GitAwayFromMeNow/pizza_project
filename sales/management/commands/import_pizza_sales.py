import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from sales.models import Pizza, PizzaVariant, Order, OrderItem


class Command(BaseCommand):
    help = (
        "Import pizza sales data from pizza_sales.csv into normalized models. "
        "Idempotent: uses source_line_id (pizza_id) to avoid duplicates."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            dest="file",
            default=str(Path(settings.BASE_DIR) / "pizza_sales.csv"),
            help="Path to pizza_sales.csv (defaults to <BASE_DIR>/pizza_sales.csv)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and validate without writing to the database.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing imported data before import (OrderItem, Order, PizzaVariant, Pizza).",
        )

    def handle(self, *args, **options):
        file_path = Path(options["file"])  # type: Path
        dry_run = options["dry_run"]
        clear = options["clear"]

        if not file_path.exists():
            raise CommandError(f"CSV file not found: {file_path}")

        self.stdout.write(self.style.NOTICE(f"Reading: {file_path}"))

        if dry_run:
            self.stdout.write(self.style.WARNING("Running in DRY-RUN mode (no DB writes)"))

        with file_path.open(newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.stdout.write(f"Rows to process: {len(rows):,}")

        @transaction.atomic
        def _import():
            if clear:
                self.stdout.write(self.style.WARNING("Clearing existing data..."))
                OrderItem.objects.all().delete()
                Order.objects.all().delete()
                PizzaVariant.objects.all().delete()
                Pizza.objects.all().delete()

            created_counts = {"pizza": 0, "variant": 0, "order": 0, "item": 0}
            skipped_items = 0

            # Simple in-memory caches to cut DB hits
            pizza_cache = {}
            variant_cache = {}
            order_cache = {}

            for i, row in enumerate(rows, start=1):
                try:
                    source_line_id = int(float(row["pizza_id"]))
                    order_id = int(float(row["order_id"]))
                    pizza_slug = row["pizza_name_id"].strip()
                    qty = int(float(row["quantity"]))
                    # Date and time
                    order_date = row["order_date"].strip()
                    order_time = row["order_time"].strip()
                    # Accept multiple date and time formats (US and EU with slashes or hyphens)
                    dt_parsed = None
                    date_formats = ["%m/%d/%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"]
                    time_formats = ["%H:%M:%S", "%H:%M"]
                    for df in date_formats:
                        for tf in time_formats:
                            try:
                                dt_parsed = datetime.strptime(f"{order_date} {order_time}", f"{df} {tf}")
                                break
                            except ValueError:
                                continue
                        if dt_parsed:
                            break
                    if not dt_parsed:
                        raise ValueError(f"time data '{order_date} {order_time}' does not match expected formats")
                    # Localize to default timezone if naive (USE_TZ=True compatibility)
                    if timezone.is_naive(dt_parsed):
                        ordered_at = timezone.make_aware(dt_parsed, timezone.get_default_timezone())
                    else:
                        ordered_at = dt_parsed
                    # Prices
                    unit_price = Decimal(str(row["unit_price"]))
                    total_price = Decimal(str(row["total_price"]))
                    size = row["pizza_size"].strip()
                    category = row["pizza_category"].strip()
                    ingredients = row["pizza_ingredients"].strip()
                    name = row["pizza_name"].strip()
                except (KeyError, ValueError, InvalidOperation) as e:
                    skipped_items += 1
                    self.stdout.write(self.style.WARNING(f"Skipping row {i}: parse error: {e}"))
                    continue

                # Pizza
                pizza_key = (name, category, ingredients)
                pizza = pizza_cache.get(pizza_key)
                if not pizza:
                    pizza, created = Pizza.objects.get_or_create(
                        name=name,
                        category=category,
                        defaults={"ingredients": ingredients},
                    )
                    # If exists but ingredients are empty and csv has it, update lightly
                    if not created and not pizza.ingredients and ingredients:
                        pizza.ingredients = ingredients
                        pizza.save(update_fields=["ingredients"])
                    if created:
                        created_counts["pizza"] += 1
                    pizza_cache[pizza_key] = pizza

                # Variant
                variant_key = (pizza.id, size)
                variant = variant_cache.get(variant_key)
                if not variant:
                    variant, v_created = PizzaVariant.objects.get_or_create(
                        pizza=pizza,
                        size=size,
                        defaults={
                            "slug": pizza_slug,
                            "unit_price": unit_price,
                        },
                    )
                    if not v_created:
                        # Ensure slug is set and unit_price reflects latest seen
                        updated = False
                        if not variant.slug:
                            variant.slug = pizza_slug
                            updated = True
                        if variant.unit_price != unit_price:
                            variant.unit_price = unit_price
                            updated = True
                        if updated:
                            variant.save(update_fields=["slug", "unit_price"])
                    else:
                        created_counts["variant"] += 1
                    variant_cache[variant_key] = variant

                # Order
                order = order_cache.get(order_id)
                if not order:
                    order, o_created = Order.objects.get_or_create(
                        external_id=order_id,
                        defaults={"ordered_at": ordered_at},
                    )
                    if not o_created and order.ordered_at != ordered_at:
                        # Keep the earliest timestamp if discrepancies appear
                        if ordered_at < order.ordered_at:
                            order.ordered_at = ordered_at
                            order.save(update_fields=["ordered_at"])
                    if o_created:
                        created_counts["order"] += 1
                    order_cache[order_id] = order

                # OrderItem (idempotent by source_line_id)
                item, item_created = OrderItem.objects.get_or_create(
                    source_line_id=source_line_id,
                    defaults={
                        "order": order,
                        "variant": variant,
                        "quantity": qty,
                        "unit_price": unit_price,
                        "total_price": total_price,
                    },
                )
                if not item_created:
                    # If exists, reconcile basic fields if different
                    updated_fields = []
                    if item.order_id != order.id:
                        item.order = order
                        updated_fields.append("order")
                    if item.variant_id != variant.id:
                        item.variant = variant
                        updated_fields.append("variant")
                    if item.quantity != qty:
                        item.quantity = qty
                        updated_fields.append("quantity")
                    if item.unit_price != unit_price:
                        item.unit_price = unit_price
                        updated_fields.append("unit_price")
                    if item.total_price != total_price:
                        item.total_price = total_price
                        updated_fields.append("total_price")
                    if updated_fields:
                        item.save(update_fields=updated_fields)
                else:
                    created_counts["item"] += 1

            return created_counts, skipped_items

        if dry_run:
            # Wrap import in atomic and rollback
            with transaction.atomic():
                created_counts, skipped_items = _import()
                self.stdout.write(self.style.WARNING("Dry-run complete, rolling back changes."))
                transaction.set_rollback(True)
        else:
            created_counts, skipped_items = _import()

        self.stdout.write(self.style.SUCCESS(
            "Import finished: "
            f"Pizzas created: {created_counts['pizza']}, "
            f"Variants created: {created_counts['variant']}, "
            f"Orders created: {created_counts['order']}, "
            f"Items created: {created_counts['item']}. "
            f"Rows skipped: {skipped_items}."
        ))
