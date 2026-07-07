from rest_framework import serializers

from apps.whatsapp.models import WhatsAppOptIn, WhatsAppTemplate


class WhatsAppTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppTemplate
        fields = [
            "id", "name", "meta_template_name", "category",
            "language", "variables", "is_active",
        ]
        read_only_fields = ["id"]


class WhatsAppOptInSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = WhatsAppOptIn
        fields = ["id", "patient", "channel", "opted_in_at", "revoked_at", "is_active"]
        read_only_fields = ["id", "opted_in_at", "revoked_at", "is_active"]

    def validate_patient(self, value):
        if value.tenant_id != self.context["request"].tenant.id:
            raise serializers.ValidationError("El paciente no pertenece a esta clínica.")
        return value
