from django.contrib import admin

from apps.clinical.models import (
    ClinicalRecord,
    Diagnosis,
    Evolution,
    TreatmentPlan,
    TreatmentPlanItem,
)


@admin.register(Evolution)
class EvolutionAdmin(admin.ModelAdmin):
    list_display = ["patient", "type", "date", "doctor", "visible_to_patient"]
    list_filter = ["type", "visible_to_patient", "tenant"]
    date_hierarchy = "date"


class TreatmentPlanItemInline(admin.TabularInline):
    model = TreatmentPlanItem
    extra = 0


@admin.register(TreatmentPlan)
class TreatmentPlanAdmin(admin.ModelAdmin):
    list_display = ["patient", "status", "created_by", "created_at"]
    list_filter = ["status", "tenant"]
    inlines = [TreatmentPlanItemInline]


admin.site.register(ClinicalRecord)
admin.site.register(Diagnosis)
