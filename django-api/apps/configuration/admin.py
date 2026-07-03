from django.contrib import admin

from apps.configuration.models import Agreement, SystemParameter, Tariff, Treatment


@admin.register(Treatment)
class TreatmentAdmin(admin.ModelAdmin):
    list_display = ["name", "specialty", "base_price", "consumes_inventory", "is_active"]
    list_filter = ["specialty", "is_active", "tenant"]
    search_fields = ["name"]


@admin.register(SystemParameter)
class SystemParameterAdmin(admin.ModelAdmin):
    list_display = ["key", "value", "tenant"]
    list_filter = ["tenant"]


admin.site.register(Agreement)
admin.site.register(Tariff)
