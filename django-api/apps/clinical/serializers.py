from rest_framework import serializers

from apps.clinical.models import (
    ClinicalRecord,
    Diagnosis,
    Evolution,
    OdontogramState,
    ToothRecord,
    TreatmentPlan,
    TreatmentPlanItem,
)


class ClinicalRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicalRecord
        fields = ["id", "general_notes", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class EvolutionSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    doctor_name = serializers.CharField(source="doctor.full_name", read_only=True)

    class Meta:
        model = Evolution
        fields = [
            "id", "doctor", "doctor_name", "appointment", "type", "type_display",
            "date", "notes", "visible_to_patient", "created_at",
        ]
        read_only_fields = ["id", "created_at", "doctor_name", "doctor"]


class DiagnosisSerializer(serializers.ModelSerializer):
    class Meta:
        model = Diagnosis
        fields = [
            "id", "doctor", "tooth_fdi_code", "code", "description", "date", "created_at",
        ]
        read_only_fields = ["id", "created_at", "doctor"]


class TreatmentPlanItemSerializer(serializers.ModelSerializer):
    treatment_name = serializers.CharField(source="treatment.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = TreatmentPlanItem
        fields = [
            "id", "treatment", "treatment_name", "tooth_fdi_code",
            "order", "status", "status_display", "estimated_price",
        ]
        read_only_fields = ["id"]


class TreatmentPlanSerializer(serializers.ModelSerializer):
    items = TreatmentPlanItemSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = TreatmentPlan
        fields = [
            "id", "created_by", "status", "status_display",
            "notes", "items", "created_at",
        ]
        read_only_fields = ["id", "created_at", "items", "created_by"]


class OdontogramStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OdontogramState
        fields = ["id", "code", "label", "color", "order", "is_active"]
        read_only_fields = ["id"]


class ToothRecordSerializer(serializers.ModelSerializer):
    state_code = serializers.CharField(source="state.code", read_only=True)
    state_label = serializers.CharField(source="state.label", read_only=True)
    state_color = serializers.CharField(source="state.color", read_only=True)
    surface_display = serializers.CharField(source="get_surface_display", read_only=True)

    class Meta:
        model = ToothRecord
        fields = [
            "id", "tooth_fdi_code", "surface", "surface_display",
            "state", "state_code", "state_label", "state_color",
            "doctor", "treatment_plan_item", "date", "notes", "created_at",
        ]
        read_only_fields = ["id", "created_at", "doctor"]
