from rest_framework import generics

from apps.common.permissions import HasRole
from apps.configuration.models import Agreement, SystemParameter, Tariff, Treatment
from apps.configuration.serializers import (
    AgreementSerializer,
    SystemParameterSerializer,
    TariffSerializer,
    TreatmentSerializer,
)

CAN_MANAGE = HasRole.for_roles("admin")
CAN_VIEW = HasRole.for_roles("admin", "reception", "doctor", "auxiliary")


class _ConfigListCreate(generics.ListCreateAPIView):
    """Base: lectura para staff clínico, escritura solo admin."""

    def get_permissions(self):
        return [CAN_MANAGE()] if self.request.method == "POST" else [CAN_VIEW()]

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)


class _ConfigDetail(generics.RetrieveUpdateDestroyAPIView):
    def get_permissions(self):
        return [CAN_VIEW()] if self.request.method == "GET" else [CAN_MANAGE()]


class TreatmentListCreateView(_ConfigListCreate):
    """GET/POST /config/treatments/ — RF-CFG-02"""

    serializer_class = TreatmentSerializer
    filterset_fields = ["specialty", "is_active"]

    def get_queryset(self):
        return (
            Treatment.objects.filter(tenant=self.request.tenant)
            .select_related("specialty")
            .order_by("name")
        )


class TreatmentDetailView(_ConfigDetail):
    serializer_class = TreatmentSerializer

    def get_queryset(self):
        return Treatment.objects.filter(tenant=self.request.tenant)


class AgreementListCreateView(_ConfigListCreate):
    """GET/POST /config/agreements/ — RF-CFG-04"""

    serializer_class = AgreementSerializer

    def get_queryset(self):
        return Agreement.objects.filter(tenant=self.request.tenant).order_by("name")


class AgreementDetailView(_ConfigDetail):
    serializer_class = AgreementSerializer

    def get_queryset(self):
        return Agreement.objects.filter(tenant=self.request.tenant)


class TariffListCreateView(_ConfigListCreate):
    """GET/POST /config/tarifarios/ — RF-CFG-03"""

    serializer_class = TariffSerializer
    filterset_fields = ["treatment", "agreement"]

    def get_queryset(self):
        return Tariff.objects.filter(tenant=self.request.tenant)


class TariffDetailView(_ConfigDetail):
    serializer_class = TariffSerializer

    def get_queryset(self):
        return Tariff.objects.filter(tenant=self.request.tenant)


class SystemParameterListView(generics.ListAPIView):
    """GET /config/parameters/ — RF-CFG-05"""

    serializer_class = SystemParameterSerializer
    permission_classes = [CAN_MANAGE]

    def get_queryset(self):
        return SystemParameter.objects.filter(tenant=self.request.tenant).order_by("key")


class SystemParameterDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /config/parameters/{id}/ — el admin solo edita 'value'."""

    serializer_class = SystemParameterSerializer
    permission_classes = [CAN_MANAGE]

    def get_queryset(self):
        return SystemParameter.objects.filter(tenant=self.request.tenant)
