from rest_framework import generics, status

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


class OdontogramStateListView(generics.ListAPIView):
    """GET /api/v1/odontogram-states/ — catálogo de estados (RF-HCL-02)."""

    serializer_class = None
    permission_classes = [CAN_VIEW_CLINICAL]
    pagination_class = None  # Catálogo fijo (~12 estados), no se pagina

    def get_serializer_class(self):
        from apps.clinical.serializers import OdontogramStateSerializer
        return OdontogramStateSerializer

    def get_queryset(self):
        from apps.clinical.models import OdontogramState
        return OdontogramState.objects.filter(
            tenant=self.request.tenant, is_active=True
        ).order_by("order")


class ToothRecordListCreateView(generics.ListCreateAPIView):
    """
    GET/POST /api/v1/patients/{id}/tooth-records/ — RF-HCL-02.
    GET devuelve el historial completo; POST crea un nuevo registro
    (nunca actualiza uno existente — así se preserva la trazabilidad).
    """

    permission_classes = [CAN_EDIT_CLINICAL]
    filterset_fields = ["tooth_fdi_code", "surface"]

    def get_serializer_class(self):
        from apps.clinical.serializers import ToothRecordSerializer
        return ToothRecordSerializer

    def get_queryset(self):
        from apps.clinical.models import ToothRecord
        return ToothRecord.objects.filter(
            patient_id=self.kwargs["pk"], tenant=self.request.tenant
        ).select_related("state", "doctor").order_by("-created_at")

    def perform_create(self, serializer):
        patient = _get_patient(self.request, self.kwargs["pk"])
        doctor = _get_doctor(self.request)
        serializer.save(tenant=self.request.tenant, patient=patient, doctor=doctor)
        _audit(self.request, "create_tooth_record", "ToothRecord", patient.id)


class CurrentOdontogramView(generics.GenericAPIView):
    """
    GET /api/v1/patients/{id}/odontogram/current/ — RF-HCL-02.
    Vista calculada: el último estado vigente por cada (pieza, superficie),
    derivado del historial de ToothRecord. Esto es lo que el frontend
    dibuja como "estado actual de la boca".
    """

    permission_classes = [CAN_VIEW_CLINICAL]

    def get(self, request, pk):
        from rest_framework.response import Response

        from apps.clinical.models import ToothRecord
        from apps.clinical.serializers import ToothRecordSerializer

        patient = _get_patient(request, pk)
        # Traer todos los registros del paciente, más recientes primero;
        # nos quedamos con el primero visto por cada (pieza, superficie).
        records = (
            ToothRecord.objects.filter(patient=patient, tenant=request.tenant)
            .select_related("state", "doctor")
            .order_by("-created_at")
        )
        current = {}
        for rec in records:
            key = (rec.tooth_fdi_code, rec.surface)
            if key not in current:
                current[key] = rec

        _audit(request, "view_odontogram", "Odontogram", patient.id)
        serializer = ToothRecordSerializer(list(current.values()), many=True)
        return Response({"patient_id": str(patient.id), "teeth": serializer.data})


class RadiographPhotoListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/patients/{id}/radiographs/ — RF-HCL-06."""

    permission_classes = [CAN_EDIT_CLINICAL]
    filterset_fields = ["type", "tooth_fdi_code"]

    def get_serializer_class(self):
        from apps.clinical.serializers import RadiographPhotoSerializer
        return RadiographPhotoSerializer

    def get_queryset(self):
        from apps.clinical.models import RadiographPhoto
        return RadiographPhoto.objects.filter(
            patient_id=self.kwargs["pk"], tenant=self.request.tenant
        ).order_by("-date")

    def perform_create(self, serializer):
        patient = _get_patient(self.request, self.kwargs["pk"])
        serializer.save(
            tenant=self.request.tenant, patient=patient, uploaded_by=self.request.user
        )


class InformedConsentListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/patients/{id}/consents/ — RF-HCL-07."""

    permission_classes = [HasRole.for_roles("admin", "doctor", "reception")]

    def get_serializer_class(self):
        from apps.clinical.serializers import InformedConsentSerializer
        return InformedConsentSerializer

    def get_queryset(self):
        from apps.clinical.models import InformedConsent
        return InformedConsent.objects.filter(
            patient_id=self.kwargs["pk"], tenant=self.request.tenant
        ).order_by("-created_at")

    def perform_create(self, serializer):
        patient = _get_patient(self.request, self.kwargs["pk"])
        serializer.save(
            tenant=self.request.tenant, patient=patient, created_by=self.request.user
        )


class ConsentSignView(generics.GenericAPIView):
    """
    POST /api/v1/consents/{id}/sign/ — RF-HCL-07.
    Recibe la firma en base64, la guarda, genera el PDF con la firma
    incrustada y registra fecha/hora/IP como evidencia (registro interno).
    """

    permission_classes = [HasRole.for_roles("admin", "doctor", "reception")]

    def get_serializer_class(self):
        from apps.clinical.serializers import ConsentSignSerializer
        return ConsentSignSerializer

    def post(self, request, pk):
        import base64

        from django.core.files.base import ContentFile
        from django.utils import timezone
        from rest_framework.response import Response

        from apps.clinical.models import InformedConsent
        from apps.clinical.pdf_utils import generate_consent_pdf
        from apps.clinical.serializers import (
            ConsentSignSerializer,
            InformedConsentSerializer,
        )

        consent = generics.get_object_or_404(
            InformedConsent, pk=pk, tenant=request.tenant
        )
        serializer = ConsentSignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Decodificar la firma base64 (formato "data:image/png;base64,....")
        raw = serializer.validated_data["signature_image_base64"]
        if "," in raw:
            raw = raw.split(",", 1)[1]
        try:
            image_bytes = base64.b64decode(raw, validate=True)
            # Verificar que sea realmente una imagen legible
            from io import BytesIO

            from PIL import Image as PILImage
            PILImage.open(BytesIO(image_bytes)).verify()
        except Exception:
            return Response(
                {"detail": "La firma no es una imagen base64 válida."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Guardar la imagen de la firma
        sig_name = f"consent_{consent.id}_signature.png"
        consent.signature_image.save(sig_name, ContentFile(image_bytes), save=False)
        consent.signed_at = timezone.now()
        consent.ip_address = self._get_ip(request)
        consent.save()

        # Generar el PDF con la firma incrustada
        pdf_bytes = generate_consent_pdf(consent, consent.signature_image.path)
        pdf_name = f"consent_{consent.id}.pdf"
        consent.pdf_file.save(pdf_name, ContentFile(pdf_bytes), save=True)

        _audit(request, "sign_consent", "InformedConsent", consent.id)
        return Response(InformedConsentSerializer(consent).data)

    @staticmethod
    def _get_ip(request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")


class ClinicalHistoryExportView(generics.GenericAPIView):
    """GET /api/v1/patients/{id}/clinical-record/export-pdf/ — RF-HCL-08."""

    permission_classes = [HasRole.for_roles("admin", "doctor")]

    def get(self, request, pk):
        from django.http import HttpResponse

        from apps.clinical.models import Diagnosis, Evolution, TreatmentPlan
        from apps.clinical.pdf_utils import generate_clinical_history_pdf

        patient = _get_patient(request, pk)
        evolutions = Evolution.objects.filter(
            patient=patient, tenant=request.tenant
        ).order_by("-date")
        diagnoses = Diagnosis.objects.filter(
            patient=patient, tenant=request.tenant
        ).order_by("-date")
        plans = TreatmentPlan.objects.filter(
            patient=patient, tenant=request.tenant
        ).prefetch_related("items", "items__treatment")

        pdf_bytes = generate_clinical_history_pdf(patient, evolutions, diagnoses, plans)
        _audit(request, "export_clinical_history", "ClinicalRecord", patient.id)

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="historia_clinica_{patient.national_id}.pdf"'
        )
        return response
