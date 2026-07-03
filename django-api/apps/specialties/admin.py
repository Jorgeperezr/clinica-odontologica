from django.contrib import admin

from apps.specialties.models import Specialty


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ["name", "tenant", "is_active"]
    list_filter = ["is_active", "tenant"]
    search_fields = ["name"]
