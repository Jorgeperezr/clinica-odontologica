from rest_framework import generics

from apps.accounts.models import AuditLog
from apps.agenda.models import Doctor
from apps.clinical.models import (
    ClinicalRecord,
    Diagnosis,
    Evolution,
    TreatmentPlan,
    TreatmentPlanItem,
)
from apps.clinical.serializers import (
    ClinicalRecordSerializer,
    DiagnosisSerializer,
    EvolutionSerializer,
    TreatmentPlanItemSerializer,
    TreatmentPlanSerializer,
)
from apps.common.permissions import HasRole
from apps.patients.models import Patient

# Solo roles clínicos acceden a la historia clínica (matriz del SRS).
CAN_EDIT_CLINICAL = HasRole.for_roles("admin", "doctor", "auxiliary")
CAN_VIEW_CLINICAL = HasRole.for_roles("admin", "doctor", "auxiliary")


def _audit(request, action, entity_type, entity_id):
    """Auditoría explícita de acceso a datos clínicos (LOPDP / RNF-004)."""
    AuditLog.objects.create(
        tenant=request.tenant,
        user=request.user,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
    )


def _get_patient(request, patient_id):
    return generics.get_object_or_404(
        Patient, pk=patient_id, tenant=request.tenant, is_active=True
    )


def _get_doctor(request):
    """Obtiene el Doctor asociado al usuario actual, si aplica."""
    return Doctor.objects.filter(user=request.user, tenant=request.tenant).first()


class ClinicalRecordView(generics.RetrieveUpdateAPIView):
    """GET/PUT /api/v1/patients/{id}/clinical-record/ — RF-HCL-01."""

    serializer_class = ClinicalRecordSerializer
    permission_classes = [CAN_EDIT_CLINICAL]

    def get_object(self):
        patient = _get_patient(self.request, self.kwargs["pk"])
        record, _ = ClinicalRecord.objects.get_or_create(patient=patient)
        _audit(self.request, f"{self.request.method.lower()}_clinical_record",
               "ClinicalRecord", patient.id)
        return record


class EvolutionListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/patients/{id}/evolutions/?type= — RF-HCL-03."""

    serializer_class = EvolutionSerializer
    permission_classes = [CAN_EDIT_CLINICAL]
    filterset_fields = ["type", "visible_to_patient"]

    def get_queryset(self):
        return Evolution.objects.filter(
            patient_id=self.kwargs["pk"], tenant=self.request.tenant
        ).select_related("doctor", "doctor__user").order_by("-date", "-created_at")

    def perform_create(self, serializer):
        patient = _get_patient(self.request, self.kwargs["pk"])
        doctor = _get_doctor(self.request)
        serializer.save(tenant=self.request.tenant, patient=patient, doctor=doctor)
        _audit(self.request, "create_evolution", "Evolution", patient.id)


class DiagnosisListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/patients/{id}/diagnoses/ — RF-HCL-04."""

    serializer_class = DiagnosisSerializer
    permission_classes = [CAN_EDIT_CLINICAL]

    def get_queryset(self):
        return Diagnosis.objects.filter(
            patient_id=self.kwargs["pk"], tenant=self.request.tenant
        ).order_by("-date")

    def perform_create(self, serializer):
        patient = _get_patient(self.request, self.kwargs["pk"])
        doctor = _get_doctor(self.request)
        serializer.save(tenant=self.request.tenant, patient=patient, doctor=doctor)


class TreatmentPlanListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/patients/{id}/treatment-plans/ — RF-HCL-05."""

    serializer_class = TreatmentPlanSerializer
    permission_classes = [CAN_EDIT_CLINICAL]

    def get_queryset(self):
        return TreatmentPlan.objects.filter(
            patient_id=self.kwargs["pk"], tenant=self.request.tenant
        ).prefetch_related("items", "items__treatment").order_by("-created_at")

    def perform_create(self, serializer):
        patient = _get_patient(self.request, self.kwargs["pk"])
        doctor = _get_doctor(self.request)
        serializer.save(tenant=self.request.tenant, patient=patient, created_by=doctor)


class TreatmentPlanDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/treatment-plans/{id}/ — RF-HCL-05."""

    serializer_class = TreatmentPlanSerializer
    permission_classes = [CAN_EDIT_CLINICAL]

    def get_queryset(self):
        return TreatmentPlan.objects.filter(
            tenant=self.request.tenant
        ).prefetch_related("items")


class TreatmentPlanItemCreateView(generics.CreateAPIView):
    """POST /api/v1/treatment-plans/{id}/items/ — RF-HCL-05."""

    serializer_class = TreatmentPlanItemSerializer
    permission_classes = [CAN_EDIT_CLINICAL]

    def perform_create(self, serializer):
        plan = generics.get_object_or_404(
            TreatmentPlan, pk=self.kwargs["pk"], tenant=self.request.tenant
        )
        serializer.save(treatment_plan=plan)


class TreatmentPlanItemUpdateView(generics.UpdateAPIView):
    """
    PATCH /api/v1/treatment-plan-items/{id}/ — cambia estado del ítem.
    Al pasar a 'done' se disparará el descuento de inventario (Sprint 11).
    """

    serializer_class = TreatmentPlanItemSerializer
    permission_classes = [CAN_EDIT_CLINICAL]

    def get_queryset(self):
        return TreatmentPlanItem.objects.filter(
            treatment_plan__tenant=self.request.tenant
        )

    def perform_update(self, serializer):
        serializer.save()
        # TODO (Sprint 11): si el ítem pasa a 'done' y el tratamiento
        # consume inventario, descontar stock automáticamente (RF-INV-05).
