from rest_framework import serializers

from apps.specialties.models import Specialty, SpecialtyForm


class SpecialtySerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialty
        fields = ["id", "name", "description", "is_active"]
        read_only_fields = ["id"]

    def validate_name(self, value):
        tenant = self.context["request"].tenant
        qs = Specialty.objects.filter(tenant=tenant, name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe una especialidad con este nombre.")
        return value


class SpecialtyFormSerializer(serializers.ModelSerializer):
    specialty_name = serializers.CharField(source="specialty.name", read_only=True)

    class Meta:
        model = SpecialtyForm
        fields = [
            "id", "specialty", "specialty_name", "patient",
            "doctor", "date", "form_data", "created_at",
        ]
        read_only_fields = ["id", "created_at", "doctor", "specialty_name"]

    def validate_specialty(self, value):
        if value.tenant_id != self.context["request"].tenant.id:
            raise serializers.ValidationError("La especialidad no pertenece a esta clínica.")
        return value

    def validate_patient(self, value):
        if value.tenant_id != self.context["request"].tenant.id:
            raise serializers.ValidationError("El paciente no pertenece a esta clínica.")
        return value
