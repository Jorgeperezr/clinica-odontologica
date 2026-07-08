from django.contrib import admin

from apps.inventory.models import Batch, InventoryMovement, Product


class BatchInline(admin.TabularInline):
    model = Batch
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "unit", "min_stock", "current_stock", "is_low_stock", "is_active"]
    list_filter = ["is_active", "tenant"]
    search_fields = ["name"]
    inlines = [BatchInline]


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ["product", "batch_number", "quantity", "expiration_date"]
    list_filter = ["tenant"]
    date_hierarchy = "expiration_date"


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = ["product", "movement_type", "quantity", "reason", "date"]
    list_filter = ["movement_type", "reason", "tenant"]
    date_hierarchy = "date"
