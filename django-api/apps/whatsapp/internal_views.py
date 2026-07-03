"""
Endpoint interno que consume whatsapp-gateway (FastAPI) para reportar
eventos recibidos del webhook de Meta (05-APIs, sección 13.2).
No es un endpoint público — está protegido por X-Service-Token y solo
debe ser alcanzable dentro de la red interna del docker-compose.
"""

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.whatsapp.models import WhatsAppMessageLog


class InternalServiceTokenPermission(permissions.BasePermission):
    def has_permission(self, request):
        from django.conf import settings

        return request.headers.get("X-Service-Token") == settings.INTERNAL_SERVICE_TOKEN


class WhatsAppEventView(APIView):
    """POST /internal/whatsapp/events/ — llamado solo por whatsapp-gateway."""

    permission_classes = [InternalServiceTokenPermission]

    def post(self, request):
        event_type = request.data.get("event_type")

        if event_type == "message_status":
            WhatsAppMessageLog.objects.filter(
                provider_message_id=request.data.get("provider_message_id")
            ).update(status=request.data.get("status"))

        # TODO (Sprint 10): manejar "inbound_message" (confirmación de
        # cita vía respuesta del paciente) y "otp_delivery_failed".

        return Response({"received": True}, status=status.HTTP_200_OK)
