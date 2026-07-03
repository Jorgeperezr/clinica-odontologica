from rest_framework import generics

from apps.common.permissions import HasRole
from apps.specialties.models import Specialty
from apps.specialties.serializers import SpecialtySerializer

# Configuración es solo-admin para escritura; lectura para todo el staff
# clínico (necesitan ver especialidades al agendar/tratar).
CAN_MANAGE = HasRole.for_roles("admin")
CAN_VIEW = HasRole.for_roles("admin", "reception", "doctor", "auxiliary")


class SpecialtyListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/specialties/ y /config/specialties/ — RF-CFG-01, RF-ESP."""

    serializer_class = SpecialtySerializer

    def get_permissions(self):
        return [CAN_MANAGE()] if self.request.method == "POST" else [CAN_VIEW()]

    def get_queryset(self):
        return Specialty.objects.filter(tenant=self.request.tenant).order_by("name")

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)


class SpecialtyDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SpecialtySerializer

    def get_permissions(self):
        return [CAN_VIEW()] if self.request.method == "GET" else [CAN_MANAGE()]

    def get_queryset(self):
        return Specialty.objects.filter(tenant=self.request.tenant)

    def perform_destroy(self, instance):
        # No se borra físicamente si tiene tratamientos asociados; se
        # desactiva. PROTECT en Treatment.specialty evita el borrado real.
        instance.is_active = False
        instance.save(update_fields=["is_active"])
