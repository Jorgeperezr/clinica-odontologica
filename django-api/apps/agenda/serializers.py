from django.utils import timezone
from rest_framework import serializers

from apps.agenda.models import Appointment, Doctor


class DoctorSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = Doctor
        fields = ["id", "user", "email", "full_name", "specialties", "calendar_color", "is_active"]
        read_only_fields = ["id"]


class AppointmentSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source="patient.full_name", read_only=True)
    doctor_name = serializers.CharField(source="doctor.full_name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id", "patient", "patient_name", "doctor", "doctor_name",
            "treatment", "scheduled_start", "scheduled_end",
            "status", "status_display", "notes",
            "checkin_at", "checkout_at", "created_at",
        ]
        read_only_fields = ["id", "checkin_at", "checkout_at", "created_at", "status"]

    def validate(self, attrs):
        start = attrs.get("scheduled_start")
        end = attrs.get("scheduled_end")
        if start and end:
            if end <= start:
                raise serializers.ValidationError(
                    "La hora de fin debe ser posterior a la de inicio."
                )
            if start < timezone.now() and not self.instance:
                raise serializers.ValidationError(
                    "No se puede agendar una cita en el pasado."
                )

        # Validar solapamiento con el doctor
        doctor = attrs.get("doctor") or (self.instance.doctor if self.instance else None)
        if doctor and start and end:
            temp = Appointment(
                doctor=doctor, scheduled_start=start, scheduled_end=end,
                pk=self.instance.pk if self.instance else None,
            )
            if temp.overlaps_with_existing():
                raise serializers.ValidationError(
                    "El doctor ya tiene una cita en ese horario."
                )
        return attrs

    def validate_patient(self, value):
        if value.tenant_id != self.context["request"].tenant.id:
            raise serializers.ValidationError("El paciente no pertenece a esta clínica.")
        return value


class RescheduleSerializer(serializers.Serializer):
    new_start = serializers.DateTimeField()
    new_end = serializers.DateTimeField()
