from django.db.models import Count, Min, Q
from rest_framework import generics

from apps.accounts.models import AuditLog
from apps.common.permissions import HasRole
from apps.patients.models import MedicalBackground, Patient, PatientDocument
from apps.patients.serializers import (
    MedicalBackgroundSerializer,
    PatientDocumentSerializer,
    PatientListSerializer,
    PatientSerializer,
)

# Roles que pueden ver pacientes (matriz del SRS, sección 4)
CAN_VIEW = HasRole.for_roles("admin", "reception", "doctor", "auxiliary")
CAN_EDIT_PATIENT = HasRole.for_roles("admin", "reception")
CAN_EDIT_MEDICAL = HasRole.for_roles("admin", "doctor", "auxiliary")


class PatientListCreateView(generics.ListCreateAPIView):
    """
    GET/POST /api/v1/patients/ — RF-PAC-01, RF-PAC-06.
    Búsqueda por nombre, cédula o teléfono vía ?search=
    """

    def get_serializer_class(self):
        return PatientListSerializer if self.request.method == "GET" else PatientSerializer

    def get_permissions(self):
        # Crear paciente: solo admin/recepción. Listar: todos los roles clínicos.
        if self.request.method == "POST":
            return [CAN_EDIT_PATIENT()]
        return [CAN_VIEW()]

    # Ordenamientos permitidos (RF-PAC-01, mejora de usabilidad).
    # No cambia la lógica de negocio: solo el order_by del listado.
    ORDERING_MAP = {
        "created_desc": ["-created_at"],
        "created_asc": ["created_at"],
        "name_asc": ["last_name", "first_name"],
        "name_desc": ["-last_name", "-first_name"],
        "attention_desc": ["-attention_count", "last_name"],
        "attention_asc": ["attention_count", "last_name"],
        "next_appt_asc": ["next_appointment", "last_name"],
    }

    def get_queryset(self):
        from django.utils import timezone

        qs = Patient.objects.filter(tenant=self.request.tenant, is_active=True)
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(national_id__icontains=search)
                | Q(phone__icontains=search)
            )

        # Anotaciones para ordenar/mostrar: nº de atenciones y próxima cita.
        qs = qs.annotate(
            attention_count=Count("appointments", distinct=True),
            next_appointment=Min(
                "appointments__scheduled_start",
                filter=Q(appointments__scheduled_start__gte=timezone.now()),
            ),
        )

        order = self.request.query_params.get("ordering", "name_asc")
        fields = self.ORDERING_MAP.get(order, self.ORDERING_MAP["name_asc"])
        # Los NULL de próxima cita van al final (pacientes sin cita futura).
        if order == "next_appt_asc":
            from django.db.models import F
            return qs.order_by(F("next_appointment").asc(nulls_last=True), "last_name")
        return qs.order_by(*fields)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)


class PatientDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /api/v1/patients/{id}/"""

    serializer_class = PatientSerializer

    def get_permissions(self):
        if self.request.method in ("PATCH", "PUT", "DELETE"):
            return [CAN_EDIT_PATIENT()]
        return [CAN_VIEW()]

    def get_queryset(self):
        return Patient.objects.filter(tenant=self.request.tenant, is_active=True)

    def perform_destroy(self, instance):
        instance.soft_delete()  # baja lógica, nunca DELETE físico


class MedicalBackgroundView(generics.RetrieveUpdateAPIView):
    """
    GET/PUT /api/v1/patients/{id}/medical-background/ — RF-PAC-03.
    Recepción no tiene acceso a datos clínicos (matriz del SRS).
    """

    serializer_class = MedicalBackgroundSerializer
    permission_classes = [CAN_EDIT_MEDICAL]

    def get_object(self):
        patient = generics.get_object_or_404(
            Patient, pk=self.kwargs["pk"], tenant=self.request.tenant, is_active=True
        )
        background, _ = MedicalBackground.objects.get_or_create(patient=patient)
        # Auditoría explícita: el acceso a datos clínicos se registra
        # siempre, incluso en lectura (exigencia LOPDP / SRS RNF-004).
        AuditLog.objects.create(
            tenant=self.request.tenant,
            user=self.request.user,
            action="view_medical_background" if self.request.method == "GET" else "update_medical_background",
            entity_type="MedicalBackground",
            entity_id=str(patient.id),
        )
        return background

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class PatientDocumentListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/patients/{id}/documents/ — RF-PAC-04."""

    serializer_class = PatientDocumentSerializer
    permission_classes = [HasRole.for_roles("admin", "reception", "doctor")]

    def get_queryset(self):
        return PatientDocument.objects.filter(
            patient_id=self.kwargs["pk"],
            patient__tenant=self.request.tenant,
            is_active=True,
        ).order_by("-uploaded_at")

    def perform_create(self, serializer):
        patient = generics.get_object_or_404(
            Patient, pk=self.kwargs["pk"], tenant=self.request.tenant
        )
        serializer.save(patient=patient, uploaded_by=self.request.user)


class PatientTreatmentHistoryView(generics.GenericAPIView):
    """
    GET /api/v1/patients/{id}/treatment-history/ — RF-PAC-05.

    Línea de tiempo consolidada. En el Sprint 1 devuelve la estructura
    base; se enriquece cuando existan las apps clinical y billing
    (Sprints 4-9) agregando evoluciones, planes y pagos a la misma
    respuesta, sin cambiar el contrato de este endpoint.
    """

    permission_classes = [CAN_VIEW]

    def get(self, request, pk):
        patient = generics.get_object_or_404(
            Patient, pk=pk, tenant=request.tenant, is_active=True
        )
        from rest_framework.response import Response

        return Response(
            {
                "patient_id": str(patient.id),
                "full_name": patient.full_name,
                "timeline": [],  # se poblará con evoluciones/planes/pagos en sprints posteriores
            }
        )
