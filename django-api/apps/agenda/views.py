from datetime import timedelta

from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.agenda.models import Appointment, Doctor
from apps.agenda.serializers import (
    AppointmentSerializer,
    DoctorSerializer,
    RescheduleSerializer,
)
from apps.common.permissions import HasRole

CAN_MANAGE_AGENDA = HasRole.for_roles("admin", "reception")
CAN_VIEW_AGENDA = HasRole.for_roles("admin", "reception", "doctor", "auxiliary")


class DoctorListView(generics.ListAPIView):
    """GET /api/v1/doctors/ — listado de doctores activos."""

    serializer_class = DoctorSerializer
    permission_classes = [CAN_VIEW_AGENDA]

    def get_queryset(self):
        return Doctor.objects.filter(
            tenant=self.request.tenant, is_active=True
        ).select_related("user")


class AppointmentListCreateView(generics.ListCreateAPIView):
    """
    GET/POST /api/v1/appointments/ — RF-AGN-03.
    Filtros: ?doctor_id=&status=&date_from=&date_to=
    """

    serializer_class = AppointmentSerializer
    filterset_fields = ["doctor", "status", "patient"]

    def get_permissions(self):
        return [CAN_MANAGE_AGENDA()] if self.request.method == "POST" else [CAN_VIEW_AGENDA()]

    def get_queryset(self):
        qs = Appointment.objects.filter(tenant=self.request.tenant).select_related(
            "patient", "doctor", "doctor__user"
        )
        # Un doctor solo ve su propia agenda por defecto
        user = self.request.user
        if user.role == "doctor":
            qs = qs.filter(doctor__user=user)

        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if date_from:
            qs = qs.filter(scheduled_start__date__gte=parse_date(date_from))
        if date_to:
            qs = qs.filter(scheduled_start__date__lte=parse_date(date_to))
        return qs.order_by("scheduled_start")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Bloqueo por morosidad (RF-AGN-07 / RN-AGN-01): antes de crear la
        # cita se verifica que el paciente no esté moroso. La regla vive en
        # el backend, no en el cliente, para que aplique igual desde la web
        # o la app. Admin/recepción pueden forzar con override=true (excepción
        # manual documentada en el SRS).
        from apps.billing.services import is_patient_delinquent

        patient = serializer.validated_data["patient"]
        override = str(request.data.get("override", "")).lower() in ("true", "1", "yes")

        if not override and is_patient_delinquent(patient, request.tenant):
            return Response(
                {
                    "error": {
                        "code": "patient_delinquent",
                        "message": (
                            "El paciente tiene cuotas vencidas. Regularice el pago o "
                            "use override=true para agendar de todas formas."
                        ),
                    }
                },
                status=status.HTTP_409_CONFLICT,
            )

        serializer.save(tenant=request.tenant, created_by=request.user)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class AppointmentDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/appointments/{id}/"""

    serializer_class = AppointmentSerializer

    def get_permissions(self):
        return [CAN_VIEW_AGENDA()] if self.request.method == "GET" else [CAN_MANAGE_AGENDA()]

    def get_queryset(self):
        return Appointment.objects.filter(tenant=self.request.tenant)


class _AppointmentActionView(APIView):
    """Base para acciones de cambio de estado sobre una cita."""

    permission_classes = [CAN_MANAGE_AGENDA]

    def get_appointment(self, request, pk):
        return generics.get_object_or_404(
            Appointment, pk=pk, tenant=request.tenant
        )


class AppointmentConfirmView(_AppointmentActionView):
    """POST /appointments/{id}/confirm/ — RF-AGN-04."""

    def post(self, request, pk):
        appt = self.get_appointment(request, pk)
        appt.status = Appointment.Status.CONFIRMED
        appt.save(update_fields=["status"])
        return Response(AppointmentSerializer(appt).data)


class AppointmentCancelView(_AppointmentActionView):
    """POST /appointments/{id}/cancel/ — RF-AGN-04."""

    def post(self, request, pk):
        appt = self.get_appointment(request, pk)
        appt.status = Appointment.Status.CANCELLED
        appt.save(update_fields=["status"])
        return Response(AppointmentSerializer(appt).data)


class AppointmentRescheduleView(_AppointmentActionView):
    """POST /appointments/{id}/reschedule/ — RF-AGN-04."""

    def post(self, request, pk):
        appt = self.get_appointment(request, pk)
        serializer = RescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_start = serializer.validated_data["new_start"]
        new_end = serializer.validated_data["new_end"]

        if new_end <= new_start:
            return Response(
                {"detail": "La hora de fin debe ser posterior a la de inicio."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validar solapamiento en el nuevo horario
        appt.scheduled_start = new_start
        appt.scheduled_end = new_end
        if appt.overlaps_with_existing():
            return Response(
                {"detail": "El doctor ya tiene una cita en ese horario."},
                status=status.HTTP_409_CONFLICT,
            )
        appt.status = Appointment.Status.RESCHEDULED
        appt.save(update_fields=["scheduled_start", "scheduled_end", "status"])
        return Response(AppointmentSerializer(appt).data)


class AppointmentCheckinView(_AppointmentActionView):
    """POST /appointments/{id}/checkin/ — RF-AGN-05.
    Dispara aviso al doctor por WhatsApp (RF-WSP-05) — se activa en Sprint 10."""

    def post(self, request, pk):
        appt = self.get_appointment(request, pk)
        appt.checkin_at = timezone.now()
        appt.save(update_fields=["checkin_at"])
        # Aviso al doctor por WhatsApp de que su paciente llegó (RF-WSP-05).
        # Se dispara de forma asíncrona (Celery) para no bloquear el check-in.
        # Si el broker no está disponible, el check-in NO debe fallar: el
        # aviso es secundario, el registro de llegada es lo crítico.
        try:
            from apps.whatsapp.tasks import notify_doctor_patient_arrived

            notify_doctor_patient_arrived.delay(str(appt.id))
        except Exception:
            pass
        return Response(AppointmentSerializer(appt).data)


class AppointmentCheckoutView(_AppointmentActionView):
    """POST /appointments/{id}/checkout/ — RF-AGN-05."""

    permission_classes = [HasRole.for_roles("admin", "reception", "doctor")]

    def post(self, request, pk):
        appt = self.get_appointment(request, pk)
        appt.checkout_at = timezone.now()
        appt.status = Appointment.Status.COMPLETED
        appt.save(update_fields=["checkout_at", "status"])
        return Response(AppointmentSerializer(appt).data)


class AgendaViewList(generics.ListAPIView):
    """
    GET /api/v1/agenda/view/?mode=daily|weekly|monthly&doctor_id=&date=
    Vista consolidada de la agenda (RF-AGN-01, 02). Devuelve las citas
    del rango correspondiente al modo y fecha ancla.
    """

    serializer_class = AppointmentSerializer
    permission_classes = [CAN_VIEW_AGENDA]

    def get_queryset(self):
        mode = self.request.query_params.get("mode", "daily")
        date_str = self.request.query_params.get("date")
        anchor = parse_date(date_str) if date_str else timezone.now().date()

        if mode == "weekly":
            start = anchor - timedelta(days=anchor.weekday())
            end = start + timedelta(days=6)
        elif mode == "monthly":
            start = anchor.replace(day=1)
            next_month = (start + timedelta(days=32)).replace(day=1)
            end = next_month - timedelta(days=1)
        else:  # daily
            start = end = anchor

        qs = Appointment.objects.filter(
            tenant=self.request.tenant,
            scheduled_start__date__gte=start,
            scheduled_start__date__lte=end,
        ).select_related("patient", "doctor", "doctor__user")

        doctor_id = self.request.query_params.get("doctor_id")
        if doctor_id:
            qs = qs.filter(doctor_id=doctor_id)

        user = self.request.user
        if user.role == "doctor":
            qs = qs.filter(doctor__user=user)

        return qs.order_by("scheduled_start")
