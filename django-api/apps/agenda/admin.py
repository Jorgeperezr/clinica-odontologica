from django.contrib import admin

from apps.agenda.models import Appointment, Doctor


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ["full_name", "tenant", "is_active"]
    list_filter = ["is_active", "tenant"]
    filter_horizontal = ["specialties"]


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ["patient", "doctor", "scheduled_start", "status"]
    list_filter = ["status", "doctor", "tenant"]
    date_hierarchy = "scheduled_start"
    search_fields = ["patient__first_name", "patient__last_name"]
