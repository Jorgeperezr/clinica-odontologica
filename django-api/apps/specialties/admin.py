from django.contrib import admin

from apps.specialties.models import Specialty, SpecialtyForm


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ["name", "tenant", "is_active"]
    list_filter = ["is_active", "tenant"]
    search_fields = ["name"]


@admin.register(SpecialtyForm)
class SpecialtyFormAdmin(admin.ModelAdmin):
    list_display = ["specialty", "patient", "doctor", "date"]
    list_filter = ["specialty", "tenant"]
    date_hierarchy = "date"
