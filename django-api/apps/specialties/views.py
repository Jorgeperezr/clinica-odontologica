from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.agenda.models import Doctor
from apps.common.permissions import HasRole
from apps.patients.models import Patient
from apps.specialties.models import (
    SPECIALTY_FORM_TEMPLATES,
    Specialty,
    SpecialtyForm,
)
from apps.specialties.serializers import (
    SpecialtyFormSerializer,
    SpecialtySerializer,
)

CAN_MANAGE = HasRole.for_roles("admin")
CAN_VIEW = HasRole.for_roles("admin", "reception", "doctor", "auxiliary")
CAN_FILL_FORM = HasRole.for_roles("admin", "doctor")


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
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class SpecialtyFormTemplateView(APIView):
    """
    GET /api/v1/specialties/{id}/form-template/ — RF-ESP-02.
    Devuelve la plantilla de campos sugerida para la especialidad, para
    que el frontend sepa qué campos mostrar. Si la especialidad no tiene
    plantilla definida, devuelve una lista vacía (formulario libre).
    """

    permission_classes = [CAN_VIEW]

    def get(self, request, pk):
        specialty = generics.get_object_or_404(
            Specialty, pk=pk, tenant=request.tenant
        )
        template = SPECIALTY_FORM_TEMPLATES.get(specialty.name, [])
        return Response({"specialty": specialty.name, "fields": template})


class PatientSpecialtyFormListCreateView(generics.ListCreateAPIView):
    """
    GET/POST /api/v1/patients/{id}/specialty-forms/?specialty= — RF-ESP-01.
    Registra el formulario clínico específico de una especialidad.
    """

    serializer_class = SpecialtyFormSerializer
    permission_classes = [CAN_FILL_FORM]
    filterset_fields = ["specialty"]

    def get_queryset(self):
        return SpecialtyForm.objects.filter(
            patient_id=self.kwargs["pk"], tenant=self.request.tenant
        ).select_related("specialty", "doctor").order_by("-date")

    def perform_create(self, serializer):
        patient = generics.get_object_or_404(
            Patient, pk=self.kwargs["pk"], tenant=self.request.tenant, is_active=True
        )
        doctor = Doctor.objects.filter(
            user=self.request.user, tenant=self.request.tenant
        ).first()
        serializer.save(tenant=self.request.tenant, patient=patient, doctor=doctor)


class SpecialtyFormDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/specialty-forms/{id}/ — RF-ESP-01."""

    serializer_class = SpecialtyFormSerializer
    permission_classes = [CAN_FILL_FORM]

    def get_queryset(self):
        return SpecialtyForm.objects.filter(tenant=self.request.tenant)
