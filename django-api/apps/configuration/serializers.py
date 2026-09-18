from rest_framework import serializers

from apps.configuration.models import Agreement, DocumentAppearance, SystemParameter, Tariff, Treatment


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
    patient_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Agreement
        fields = ["id", "name", "discount_percentage", "is_active", "patient_count"]
        read_only_fields = ["id"]

    def validate_discount_percentage(self, value):
        """
        Un descuento fuera de [0, 100] no significa nada: por encima de 100
        la clínica pagaría al paciente y por debajo de 0 le cobraría un
        recargo disfrazado de convenio. `price_for` lo recorta igualmente,
        pero conviene que no llegue a guardarse mal.
        """
        if value is not None and not (0 <= value <= 100):
            raise serializers.ValidationError("El descuento debe estar entre 0 y 100 %.")
        return value


class TariffSerializer(serializers.ModelSerializer):
    treatment_name = serializers.CharField(source="treatment.name", read_only=True)
    agreement_name = serializers.CharField(source="agreement.name", read_only=True,
                                           default=None)

    class Meta:
        model = Tariff
        fields = ["id", "treatment", "treatment_name", "agreement", "agreement_name",
                  "price"]
        read_only_fields = ["id"]

    # El `queryset` que DRF deduce de un ForeignKey NO filtra por tenant: son
    # todos los tratamientos y convenios de todas las clínicas. Sin estas dos
    # comprobaciones, un administrador podía crear un tarifario propio
    # apuntando al tratamiento de otra clínica — la fila se guardaba con su
    # propio tenant, así que pasaba los filtros de lectura, y el nombre del
    # tratamiento ajeno aparecía en su rejilla de precios.

    def validate_treatment(self, value):
        if value.tenant_id != self.context["request"].tenant.id:
            raise serializers.ValidationError("El tratamiento no pertenece a esta clínica.")
        return value

    def validate_agreement(self, value):
        if value is not None and value.tenant_id != self.context["request"].tenant.id:
            raise serializers.ValidationError("El convenio no pertenece a esta clínica.")
        return value

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("El precio no puede ser negativo.")
        return value


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
