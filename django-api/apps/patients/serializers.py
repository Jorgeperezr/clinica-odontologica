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
    class Meta:
        model = PatientDocument
        fields = ["id", "doc_type", "file", "description", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]


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
    """Versión ligera para listados/búsqueda (RF-PAC-06)."""

    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Patient
        fields = ["id", "full_name", "national_id", "phone"]
