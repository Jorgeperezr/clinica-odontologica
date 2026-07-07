from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import HasRole
from apps.whatsapp.models import WhatsAppOptIn, WhatsAppTemplate
from apps.whatsapp.serializers import (
    WhatsAppOptInSerializer,
    WhatsAppTemplateSerializer,
)

CAN_MANAGE = HasRole.for_roles("admin")
CAN_MANAGE_OPTIN = HasRole.for_roles("admin", "reception")


class WhatsAppTemplateListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/config/whatsapp-templates/ — RN-WSP-01."""

    serializer_class = WhatsAppTemplateSerializer
    permission_classes = [CAN_MANAGE]

    def get_queryset(self):
        return WhatsAppTemplate.objects.filter(tenant=self.request.tenant).order_by("name")

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)


class WhatsAppOptInListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/patients/{id}/whatsapp-optin/ — RN-WSP-02."""

    serializer_class = WhatsAppOptInSerializer
    permission_classes = [CAN_MANAGE_OPTIN]

    def get_queryset(self):
        return WhatsAppOptIn.objects.filter(
            patient_id=self.kwargs["pk"], tenant=self.request.tenant
        ).order_by("-opted_in_at")

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant, patient_id=self.kwargs["pk"])


class WhatsAppOptInRevokeView(APIView):
    """POST /api/v1/whatsapp-optin/{id}/revoke/ — revoca el consentimiento."""

    permission_classes = [CAN_MANAGE_OPTIN]

    def post(self, request, pk):
        from django.utils import timezone

        optin = generics.get_object_or_404(
            WhatsAppOptIn, pk=pk, tenant=request.tenant
        )
        optin.revoked_at = timezone.now()
        optin.save(update_fields=["revoked_at"])
        return Response(WhatsAppOptInSerializer(optin).data)
