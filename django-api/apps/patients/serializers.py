from rest_framework import serializers

from apps.patients.models import MedicalBackground, Patient, PatientDocument


class MedicalBackgroundSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalBackground
        fields = [
            "allergies", "medications", "conditions",
            "is_pregnant", "updated_at",
        ]
        read_only_fields = ["updated_at"]


class PatientDocumentSerializer(serializers.ModelSerializer):
    # URL RELATIVA (p. ej. "/media/patients/documents/x.pdf"): el frontend la
    # resuelve contra apiBase(), evitando el host interno (localhost) que el
    # navegador bloquea por Mixed Content en https. Reemplaza al antiguo
    # campo "file" absoluto que impedía visualizar los documentos.
    file_url = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()
    doc_type_display = serializers.CharField(source="get_doc_type_display", read_only=True)
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = PatientDocument
        fields = [
            "id", "doc_type", "doc_type_display", "file", "file_url", "file_name",
            "file_size", "description", "uploaded_at", "uploaded_by_name",
        ]
        read_only_fields = ["id", "uploaded_at"]
        extra_kwargs = {"file": {"write_only": True}}

    def get_file_url(self, obj):
        return obj.file.url if obj.file else None

    def get_file_name(self, obj):
        import os
        return os.path.basename(obj.file.name) if obj.file else ""

    def get_file_size(self, obj):
        try:
            return obj.file.size if obj.file else 0
        except (OSError, ValueError):
            return 0

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return obj.uploaded_by.full_name or obj.uploaded_by.email
        return "—"


class PatientSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Patient
        fields = [
            "id", "first_name", "last_name", "full_name", "national_id",
            "birth_date", "phone", "email", "address", "photo", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_national_id(self, value):
        tenant = self.context["request"].tenant
        qs = Patient.objects.filter(tenant=tenant, national_id=value, is_active=True)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "Ya existe un paciente activo con esta identificación."
            )
        return value


class PatientListSerializer(serializers.ModelSerializer):
    attention_count = serializers.IntegerField(read_only=True, default=0)
    next_appointment = serializers.DateTimeField(read_only=True, allow_null=True)
    """Versión ligera para listados/búsqueda (RF-PAC-06)."""

    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Patient
        fields = ["id", "full_name", "national_id", "phone", "created_at",
                  "attention_count", "next_appointment"]
