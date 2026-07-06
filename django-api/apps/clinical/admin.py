from django.contrib import admin

from apps.clinical.models import (
    ClinicalRecord,
    Diagnosis,
    Evolution,
    OdontogramState,
    ToothRecord,
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


@admin.register(OdontogramState)
class OdontogramStateAdmin(admin.ModelAdmin):
    list_display = ["code", "label", "color", "order", "is_active", "tenant"]
    list_filter = ["is_active", "tenant"]


@admin.register(ToothRecord)
class ToothRecordAdmin(admin.ModelAdmin):
    list_display = ["patient", "tooth_fdi_code", "surface", "state", "date", "doctor"]
    list_filter = ["state", "tenant"]
    date_hierarchy = "date"


admin.site.register(ClinicalRecord)
admin.site.register(Diagnosis)
