"""
Sprint 23 — Historia Clínica Odontológica según formulario MSP
HCU-form.033/2021: registro por consulta (B-G, I), catálogo CIE-10 con
búsqueda (N), pedidos e informes de exámenes (L/M) y datos del
profesional guardados automáticamente desde la credencial (O).
"""

from django.utils import timezone
from rest_framework import generics, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.agenda.models import Doctor
from apps.clinical.models import Cie10, ExamRequest, Form033Record
from apps.common.permissions import HasRole

CAN_EDIT_CLINICAL = HasRole.for_roles("admin", "doctor", "auxiliary")
CAN_VIEW_CLINICAL = HasRole.for_roles("admin", "doctor", "auxiliary", "reception")


def _get_patient(request, pk):
    from apps.patients.models import Patient
    return Patient.objects.get(id=pk, tenant=request.tenant)


def _professional_snapshot(request):
    """Literal O: se arma SOLO desde la credencial autenticada (oculto en la UI)."""
    user = request.user
    doctor = Doctor.objects.filter(tenant=request.tenant, user=user).first()
    return doctor, {
        "full_name": user.full_name or user.email,
        "email": user.email,
        "role": user.role,
        "license_number": doctor.license_number if doctor else "",
        "user_id": str(user.id),
        "recorded_at": timezone.now().isoformat(),
        "has_signature": bool(doctor.signature_image) if doctor else False,
    }


class Form033Serializer(serializers.ModelSerializer):
    registered_by = serializers.SerializerMethodField()

    class Meta:
        model = Form033Record
        fields = [
            "id", "date", "motivo_consulta", "embarazada", "enfermedad_actual",
            "antecedentes_personales", "antecedentes_familiares",
            "temperatura", "pulso", "frecuencia_respiratoria", "presion_arterial",
            "examen_estomatognatico", "indicadores_salud_bucal",
            "registered_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "registered_by", "created_at", "updated_at"]

    def get_registered_by(self, obj):
        snap = obj.professional_snapshot or {}
        name = snap.get("full_name", "")
        lic = snap.get("license_number", "")
        return f"{name}{f' · {lic}' if lic else ''}" or None


class Form033ListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/patients/{pk}/form033/ — una historia por consulta."""

    serializer_class = Form033Serializer
    pagination_class = None

    def get_permissions(self):
        return [CAN_EDIT_CLINICAL()] if self.request.method == "POST" else [CAN_VIEW_CLINICAL()]

    def get_queryset(self):
        return Form033Record.objects.filter(
            tenant=self.request.tenant, patient_id=self.kwargs["pk"]
        )

    def perform_create(self, serializer):
        patient = _get_patient(self.request, self.kwargs["pk"])
        doctor, snapshot = _professional_snapshot(self.request)
        serializer.save(
            tenant=self.request.tenant, patient=patient,
            doctor=doctor, created_by=self.request.user,
            professional_snapshot=snapshot,
        )


class Form033DetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/form033/{pk}/ — editar la historia de la consulta."""

    serializer_class = Form033Serializer
    permission_classes = [CAN_EDIT_CLINICAL]

    def get_queryset(self):
        return Form033Record.objects.filter(tenant=self.request.tenant)

    def perform_update(self, serializer):
        # Cada edición refresca la constancia del profesional (O)
        doctor, snapshot = _professional_snapshot(self.request)
        serializer.save(professional_snapshot=snapshot)


class Cie10SearchView(APIView):
    """GET /api/v1/cie10/?q= — busca por código o nombre (literal N)."""

    permission_classes = [CAN_VIEW_CLINICAL]

    def get(self, request):
        q = str(request.query_params.get("q", "")).strip()
        if len(q) < 2:
            return Response({"results": []})
        from django.db.models import Q
        matches = Cie10.objects.filter(
            Q(code__istartswith=q) | Q(description__icontains=q)
        )[:20]
        return Response({"results": [
            {"code": c.code, "description": c.description} for c in matches
        ]})


class ExamRequestSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    report_document_url = serializers.SerializerMethodField()

    class Meta:
        model = ExamRequest
        fields = [
            "id", "category", "category_display", "detail", "status", "status_display",
            "report_notes", "report_document", "report_document_url",
            "requested_at", "reported_at",
        ]
        read_only_fields = ["id", "status", "requested_at", "reported_at"]

    def get_report_document_url(self, obj):
        if obj.report_document and obj.report_document.file:
            request = self.context.get("request")
            url = obj.report_document.file.url
            return request.build_absolute_uri(url) if request else url
        return None


class ExamRequestListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/patients/{pk}/exam-requests/ — literal L."""

    serializer_class = ExamRequestSerializer
    pagination_class = None

    def get_permissions(self):
        return [CAN_EDIT_CLINICAL()] if self.request.method == "POST" else [CAN_VIEW_CLINICAL()]

    def get_queryset(self):
        return ExamRequest.objects.filter(
            tenant=self.request.tenant, patient_id=self.kwargs["pk"]
        ).select_related("report_document")

    def perform_create(self, serializer):
        patient = _get_patient(self.request, self.kwargs["pk"])
        serializer.save(tenant=self.request.tenant, patient=patient,
                        requested_by=self.request.user)


class ExamRequestReportView(APIView):
    """PATCH /api/v1/exam-requests/{pk}/report/ — literal M: adjuntar informe."""

    permission_classes = [CAN_EDIT_CLINICAL]

    def patch(self, request, pk):
        try:
            exam = ExamRequest.objects.get(id=pk, tenant=request.tenant)
        except ExamRequest.DoesNotExist:
            return Response({"detail": "Pedido no encontrado."}, status=404)

        if "report_notes" in request.data:
            exam.report_notes = str(request.data["report_notes"])
        doc_id = request.data.get("report_document")
        if doc_id:
            from apps.patients.models import PatientDocument
            doc = PatientDocument.objects.filter(
                id=doc_id, patient=exam.patient
            ).first()
            if not doc:
                return Response({"detail": "Documento inválido."}, status=400)
            exam.report_document = doc
        exam.status = ExamRequest.Status.REPORTED
        exam.reported_at = timezone.now()
        exam.save()
        return Response(ExamRequestSerializer(exam, context={"request": request}).data)
