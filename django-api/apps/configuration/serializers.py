from rest_framework import serializers

from apps.configuration.models import Agreement, SystemParameter, Tariff, Treatment, DocumentAppearance


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


class DocumentAppearanceSerializer(serializers.ModelSerializer):
    """
    Apariencia de documentos. Devuelve SIEMPRE los ajustes resueltos (con
    los valores por defecto rellenados), de modo que el panel puede pintar
    todos los controles aunque el registro se guardara antes de que
    existiera un ajuste nuevo.

    Al escribir se FUSIONA con lo guardado en vez de sustituirlo: así el
    panel puede enviar solo el grupo que el usuario ha tocado y no borra
    sin querer el resto de la configuración.
    """

    class Meta:
        model = DocumentAppearance
        fields = ("id",) + DocumentAppearance.GROUPS
        read_only_fields = ("id",)

    def to_representation(self, instance):
        data = {"id": str(instance.id)}
        data.update(instance.resolved())
        return data

    def validate(self, attrs):
        for group, value in attrs.items():
            if value is not None and not isinstance(value, dict):
                raise serializers.ValidationError(
                    {group: "Debe ser un objeto con los ajustes de ese grupo."}
                )
        return attrs

    def update(self, instance, validated_data):
        for group, value in validated_data.items():
            merged = dict(getattr(instance, group) or {})
            merged.update(value or {})
            setattr(instance, group, merged)
        instance.save()
        return instance
