from rest_framework import serializers

from apps.configuration.models import Agreement, SystemParameter, Tariff, Treatment


class TreatmentSerializer(serializers.ModelSerializer):
    specialty_name = serializers.CharField(source="specialty.name", read_only=True)

    class Meta:
        model = Treatment
        fields = [
            "id", "name", "specialty", "specialty_name",
            "base_price", "consumes_inventory", "is_active",
        ]
        read_only_fields = ["id"]

    def validate_specialty(self, value):
        # La especialidad debe pertenecer al mismo tenant del usuario.
        if value.tenant_id != self.context["request"].tenant.id:
            raise serializers.ValidationError("La especialidad no pertenece a esta clínica.")
        return value


class AgreementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agreement
        fields = ["id", "name", "discount_percentage", "is_active"]
        read_only_fields = ["id"]


class TariffSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tariff
        fields = ["id", "treatment", "agreement", "price"]
        read_only_fields = ["id"]


class SystemParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemParameter
        fields = ["id", "key", "value", "description"]
        read_only_fields = ["id", "key", "description"]
        # key y description son de solo lectura: los parámetros son un
        # catálogo fijo sembrado por bootstrap; el admin solo edita 'value'.


class ClinicBrandingSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()

    class Meta:
        from .models import ClinicBranding
        model = ClinicBranding
        fields = ["id", "logo", "logo_url", "theme", "display_name", "short_name",
                  "address", "phone", "email", "updated_at"]
        extra_kwargs = {"logo": {"write_only": True, "required": False}}

    def get_logo_url(self, obj):
        # Ruta relativa (p. ej. "/media/branding/logos/x.png"): el frontend
        # la resuelve contra el host correcto. Evita construir URLs con el
        # host interno del proxy (http://localhost) que el navegador bloquea
        # por Mixed Content al estar la página en https.
        if not obj.logo:
            return None
        return obj.logo.url
