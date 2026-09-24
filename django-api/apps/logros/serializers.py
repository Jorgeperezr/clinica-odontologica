from rest_framework import serializers

from apps.logros.models import Logro, LogroDePaciente


class LogroSerializer(serializers.ModelSerializer):
    regla_display = serializers.CharField(source="get_regla_display", read_only=True)
    es_automatico = serializers.BooleanField(read_only=True)
    concedidos = serializers.SerializerMethodField()

    class Meta:
        model = Logro
        fields = [
            "id", "nombre", "descripcion", "icono", "beneficio",
            "regla", "regla_display", "es_automatico", "meses_requeridos",
            "activo", "concedidos",
        ]
        read_only_fields = ["id"]

    def get_concedidos(self, obj):
        return obj.concesiones.count()

    def validate_nombre(self, value):
        return value.strip()


class LogroDePacienteSerializer(serializers.ModelSerializer):
    logro_nombre = serializers.CharField(source="logro.nombre", read_only=True)
    icono = serializers.CharField(source="logro.icono", read_only=True)
    beneficio = serializers.CharField(source="logro.beneficio", read_only=True)
    paciente_nombre = serializers.SerializerMethodField()
    otorgado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = LogroDePaciente
        fields = [
            "id", "patient", "paciente_nombre", "logro", "logro_nombre",
            "icono", "beneficio", "otorgado_en", "otorgado_por",
            "otorgado_por_nombre", "periodo", "nota",
        ]
        read_only_fields = ["id", "otorgado_en", "otorgado_por"]

    def get_paciente_nombre(self, obj):
        p = obj.patient
        return f"{p.first_name} {p.last_name}".strip()

    def get_otorgado_por_nombre(self, obj):
        # «El sistema» y no una cadena vacía: quien revise por qué se
        # premió tiene que poder distinguir una regla de una persona.
        return obj.otorgado_por.full_name if obj.otorgado_por else "El sistema"
