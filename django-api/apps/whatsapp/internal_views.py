"""
Endpoint interno que consume whatsapp-gateway (FastAPI) para reportar
eventos recibidos del webhook de Meta (05-APIs, sección 13.2).
No es un endpoint público — está protegido por X-Service-Token y solo
debe ser alcanzable dentro de la red interna del docker-compose.
"""

from django.conf import settings
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.whatsapp.models import WhatsAppMessageLog


class InternalServiceTokenPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        # Firma correcta de DRF: (self, request, view). En el Sprint 0
        # faltaba el parámetro 'view', lo que habría roto en runtime.
        return request.headers.get("X-Service-Token") == settings.INTERNAL_SERVICE_TOKEN


class WhatsAppEventView(APIView):
    """POST /internal/whatsapp/events/ — llamado solo por whatsapp-gateway."""

    permission_classes = [InternalServiceTokenPermission]

    def post(self, request):
        event_type = request.data.get("event_type")

        if event_type == "message_status":
            self._handle_status(request)
        elif event_type == "inbound_message":
            self._handle_inbound(request)
        # "otp_delivery_failed" se registra pero no requiere acción de dominio;
        # el reintento de OTP lo maneja el usuario reenviando desde la app.

        return Response({"received": True}, status=status.HTTP_200_OK)

    def _handle_status(self, request):
        """Actualiza el estado de entrega de un mensaje (sent/delivered/read/failed)."""
        WhatsAppMessageLog.objects.filter(
            provider_message_id=request.data.get("provider_message_id")
        ).update(status=request.data.get("status", ""))

    def _handle_inbound(self, request):
        """
        Mensaje entrante del paciente. Si es una confirmación de cita
        (respuesta afirmativa a un recordatorio), confirma la cita
        asociada — reutilizando la misma lógica que el endpoint manual
        de confirmación (RF-WSP-03).
        """
        from apps.agenda.models import Appointment

        text = str(request.data.get("text", "")).strip().lower()
        appointment_id = request.data.get("appointment_id")

        # Palabras afirmativas simples. Un flujo más rico (botones de Meta)
        # se puede añadir después sin cambiar este contrato.
        affirmatives = {"si", "sí", "confirmo", "confirmar", "ok", "yes", "1"}
        if appointment_id and text in affirmatives:
            Appointment.objects.filter(id=appointment_id).update(
                status=Appointment.Status.CONFIRMED
            )
