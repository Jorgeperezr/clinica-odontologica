from rest_framework import serializers

from apps.clinical.models import (
    ClinicalRecord,
    Diagnosis,
    Evolution,
    InformedConsent,
    OdontogramState,
    RadiographPhoto,
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
    registered_by = serializers.SerializerMethodField()

    class Meta:
        model = Evolution
        fields = [
            "id", "doctor", "doctor_name", "registered_by", "appointment",
            "type", "type_display", "date", "notes", "visible_to_patient", "follow_up_date", "created_at",
        ]
        read_only_fields = ["id", "created_at", "doctor_name", "doctor", "registered_by"]

    def get_registered_by(self, obj):
        if obj.doctor:
            return obj.doctor.full_name
        u = obj.created_by
        if not u:
            return None
        return u.full_name or u.email


class DiagnosisSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source="get_diagnosis_kind_display", read_only=True)

    class Meta:
        model = Diagnosis
        fields = [
            "id", "doctor", "tooth_fdi_code", "code", "description",
            "diagnosis_kind", "kind_display", "date", "created_at",
        ]
        read_only_fields = ["id", "created_at", "doctor", "kind_display"]


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
    progress = serializers.SerializerMethodField()

    class Meta:
        model = TreatmentPlan
        fields = [
            "id", "created_by", "status", "status_display",
            "notes", "items", "progress", "created_at",
        ]
        read_only_fields = ["id", "created_at", "items", "created_by", "progress"]

    def get_progress(self, obj):
        """Control de progreso: realizados / total y porcentaje (Sprint 22)."""
        items = list(obj.items.all())
        total = len(items)
        done = sum(1 for i in items if i.status == "done")
        return {
            "done": done, "total": total,
            "percent": round(done * 100 / total) if total else 0,
        }


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
            "mobility", "recession",
            "doctor", "treatment_plan_item", "date", "notes", "created_at",
        ]
        read_only_fields = ["id", "created_at", "doctor"]


class RadiographPhotoSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = RadiographPhoto
        fields = [
            "id", "tooth_fdi_code", "file", "type", "type_display",
            "description", "date", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class InformedConsentSerializer(serializers.ModelSerializer):
    is_signed = serializers.BooleanField(read_only=True)

    class Meta:
        model = InformedConsent
        fields = [
            "id", "patient", "treatment_plan", "title", "body_text",
            "pdf_file", "signature_image", "signed_at", "ip_address",
            "is_signed", "created_at",
            "status", "procedure", "benefits", "risks", "alternatives", "observations",]
        read_only_fields = [
            "id", "patient", "pdf_file", "signature_image",
            "signed_at", "ip_address", "is_signed", "created_at",
        ]


class ConsentSignSerializer(serializers.Serializer):
    """Recibe la firma capturada en pantalla táctil como base64 PNG."""

    signature_image_base64 = serializers.CharField()



class TemplateItemSerializer(serializers.ModelSerializer):
    treatment_name = serializers.CharField(source="treatment.name", read_only=True)
    base_price = serializers.DecimalField(
        source="treatment.base_price", max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        from apps.clinical.models import TreatmentPlanTemplateItem
        model = TreatmentPlanTemplateItem
        fields = ["id", "treatment", "treatment_name", "base_price", "order", "notes"]
        read_only_fields = ["id"]


class TreatmentPlanTemplateSerializer(serializers.ModelSerializer):
    items = TemplateItemSerializer(many=True, read_only=True)
    total_estimated = serializers.SerializerMethodField()

    class Meta:
        from apps.clinical.models import TreatmentPlanTemplate
        model = TreatmentPlanTemplate
        fields = ["id", "name", "description", "is_active", "items", "total_estimated", "created_at"]
        read_only_fields = ["id", "created_at", "items"]

    def get_total_estimated(self, obj):
        return str(sum((i.treatment.base_price for i in obj.items.all()), start=0))


class ConsentTemplateSerializer(serializers.ModelSerializer):
    procedure_display = serializers.CharField(source="get_procedure_display", read_only=True)

    class Meta:
        from apps.clinical.models import ConsentTemplate
        model = ConsentTemplate
        fields = ["id", "procedure", "procedure_display", "title", "procedure_text",
                  "benefits", "risks", "alternatives", "body_text", "created_at"]
        read_only_fields = ["id", "created_at"]


class ConsentAuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        from apps.clinical.models import ConsentAuditLog
        model = ConsentAuditLog
        fields = ["id", "action", "detail", "actor_name", "at"]

    def get_actor_name(self, obj):
        return obj.actor.full_name or obj.actor.email if obj.actor else "—"
