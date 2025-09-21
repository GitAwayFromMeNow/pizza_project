from django.contrib import admin
from .models import Pizza, PizzaVariant, Order, OrderItem


@admin.register(Pizza)
class PizzaAdmin(admin.ModelAdmin):
    list_display = ("name", "category")
    search_fields = ("name", "category", "ingredients")


@admin.register(PizzaVariant)
class PizzaVariantAdmin(admin.ModelAdmin):
    list_display = ("pizza", "size", "unit_price", "slug")
    list_filter = ("size", "pizza__category")
    search_fields = ("pizza__name", "slug")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("source_line_id",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("external_id", "ordered_at", "status", "customer_first_name", "customer_last_name", "phone")
    list_filter = ("status",)
    search_fields = ("external_id", "customer_first_name", "customer_last_name", "phone")
    date_hierarchy = "ordered_at"
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "variant", "quantity", "unit_price", "total_price", "source_line_id")
    list_filter = ("variant__size", "variant__pizza__category")
    search_fields = ("order__external_id", "variant__pizza__name", "source_line_id")
