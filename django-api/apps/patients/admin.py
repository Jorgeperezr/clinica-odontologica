from django.contrib import admin

from apps.patients.models import MedicalBackground, Patient, PatientDocument


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ["full_name", "national_id", "phone", "tenant", "is_active"]
    list_filter = ["is_active", "tenant"]
    search_fields = ["first_name", "last_name", "national_id", "phone"]


admin.site.register(MedicalBackground)
admin.site.register(PatientDocument)
