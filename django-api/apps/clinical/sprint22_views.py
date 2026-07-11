"""
Sprint 22 — vistas de: plantillas de planes (con aplicación al paciente
y presupuesto automático), alertas de seguimiento, documentos por
paciente y receta profesional en PDF.
"""

import io
from datetime import date

from django.http import FileResponse, Http404
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AuditLog
from apps.clinical.models import (
    Evolution,
    TreatmentPlan,
    TreatmentPlanItem,
    TreatmentPlanTemplate,
)
from apps.clinical.serializers import TreatmentPlanTemplateSerializer
from apps.common.permissions import HasRole

CAN_EDIT_CLINICAL = HasRole.for_roles("admin", "doctor", "auxiliary")
CAN_VIEW_CLINICAL = HasRole.for_roles("admin", "doctor", "auxiliary", "reception")
CAN_MANAGE_TEMPLATES = HasRole.for_roles("admin", "doctor")


# ──────────── 1. Plantillas de planes de tratamiento ────────────

class TemplateListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/clinical/plan-templates/"""

    serializer_class = TreatmentPlanTemplateSerializer
    pagination_class = None

    def get_permissions(self):
        return [CAN_MANAGE_TEMPLATES()] if self.request.method == "POST" else [CAN_VIEW_CLINICAL()]

    def get_queryset(self):
        return (
            TreatmentPlanTemplate.objects.filter(tenant=self.request.tenant, is_active=True)
            .prefetch_related("items__treatment")
            .order_by("name")
        )

    def perform_create(self, serializer):
        # Las plantillas nacen activas (neutraliza la semántica de checkbox
        # de formularios: boolean ausente = False).
        template = serializer.save(tenant=self.request.tenant, is_active=True)
        # Ítems opcionales en el mismo POST: [{"treatment": id, "order": n, "notes": ""}]
        from apps.clinical.models import TreatmentPlanTemplateItem
        from apps.configuration.models import Treatment

        for raw in self.request.data.get("items", []):
            try:
                treatment = Treatment.objects.get(
                    id=raw.get("treatment"), tenant=self.request.tenant
                )
            except Treatment.DoesNotExist:
                continue
            TreatmentPlanTemplateItem.objects.create(
                template=template,
                treatment=treatment,
                order=int(raw.get("order", 1)),
                notes=str(raw.get("notes", ""))[:255],
            )


class ApplyTemplateView(APIView):
    """
    POST /api/v1/patients/{pk}/apply-plan-template/ {template_id}
    Crea el plan del paciente con los ítems de la plantilla y los precios
    actuales del tarifario. Devuelve el plan creado.
    """

    permission_classes = [CAN_EDIT_CLINICAL]

    def post(self, request, pk):
        from apps.clinical.serializers import TreatmentPlanSerializer
        from apps.clinical.views import _get_doctor, _get_patient

        patient = _get_patient(request, pk)
        try:
            template = TreatmentPlanTemplate.objects.prefetch_related("items__treatment").get(
                id=request.data.get("template_id"), tenant=request.tenant
            )
        except TreatmentPlanTemplate.DoesNotExist:
            return Response({"detail": "Plantilla no encontrada."}, status=404)

        plan = TreatmentPlan.objects.create(
            tenant=request.tenant, patient=patient,
            created_by=_get_doctor(request), status="active",
            notes=f"Creado desde la plantilla: {template.name}",
        )
        for item in template.items.all():
            TreatmentPlanItem.objects.create(
                treatment_plan=plan, treatment=item.treatment,
                order=item.order, estimated_price=item.treatment.base_price,
            )
        AuditLog.objects.create(
            tenant=request.tenant, user=request.user,
            action="apply_plan_template", entity_type="TreatmentPlan",
            entity_id=str(plan.id),
            metadata={"template": template.name, "patient_id": str(patient.id)},
        )
        return Response(TreatmentPlanSerializer(plan).data, status=201)


class PlanToBudgetView(APIView):
    """
    POST /api/v1/treatment-plans/{pk}/generate-budget/
    Presupuesto automático: crea el Budget (billing) con un ítem por cada
    ítem del plan, a los precios estimados del plan. Une el flujo clínico
    con el financiero en un clic.
    """

    permission_classes = [HasRole.for_roles("admin", "reception", "doctor")]

    def post(self, request, pk):
        from apps.billing.models import Budget, BudgetItem
        from apps.billing.serializers import BudgetSerializer

        try:
            plan = TreatmentPlan.objects.prefetch_related("items__treatment").get(
                id=pk, tenant=request.tenant
            )
        except TreatmentPlan.DoesNotExist:
            return Response({"detail": "Plan no encontrado."}, status=404)

        items = list(plan.items.all())
        if not items:
            return Response({"detail": "El plan no tiene ítems."}, status=400)

        budget = Budget.objects.create(
            tenant=request.tenant, patient=plan.patient,
            notes="Generado automáticamente desde el plan de tratamiento.",
        )
        total = 0
        for item in items:
            price = item.estimated_price or item.treatment.base_price
            BudgetItem.objects.create(
                budget=budget, treatment=item.treatment,
                tooth_fdi_code=item.tooth_fdi_code or "",
                quantity=1, unit_price=price,
            )
            total += price
        budget.total_amount = total
        budget.save(update_fields=["total_amount"])

        AuditLog.objects.create(
            tenant=request.tenant, user=request.user,
            action="generate_budget_from_plan", entity_type="Budget",
            entity_id=str(budget.id),
            metadata={"plan_id": str(plan.id), "total": str(total)},
        )
        return Response(BudgetSerializer(budget).data, status=201)


# ──────────── 2. Alertas de seguimiento ────────────

class FollowUpAlertsView(APIView):
    """
    GET /api/v1/clinical/follow-ups/ — evoluciones cuya fecha de
    seguimiento ya llegó (hoy o vencida). Alimenta la alerta del dashboard
    y la línea de tiempo.
    """

    permission_classes = [CAN_VIEW_CLINICAL]

    def get(self, request):
        due = (
            Evolution.objects.filter(
                tenant=request.tenant,
                follow_up_date__isnull=False,
                follow_up_date__lte=date.today(),
            )
            .select_related("patient")
            .order_by("follow_up_date")[:50]
        )
        return Response({"results": [{
            "id": str(e.id),
            "patient_id": str(e.patient_id),
            "patient_name": e.patient.full_name,
            "follow_up_date": str(e.follow_up_date),
            "days_overdue": (date.today() - e.follow_up_date).days,
            "notes": e.notes[:120],
        } for e in due]})


# ──────────── 4. Receta profesional en PDF ────────────

class PrescriptionPDFView(APIView):
    """
    GET /api/v1/evolutions/{pk}/prescription-pdf/ — receta profesional:
    membrete de la clínica (nombre, RUC, dirección, teléfono), datos del
    doctor con su registro profesional, paciente, contenido Rx y bloque
    de firma.

    firmaEC (Fase 2): la firma electrónica legal requiere el certificado
    .p12 del doctor emitido por una entidad acreditada (Registro Civil,
    ANF, etc.). El PDF generado aquí queda listo para ese proceso — ver
    DEPLOY.md.
    """

    permission_classes = [CAN_VIEW_CLINICAL]

    def get(self, request, pk):
        from reportlab.lib.pagesizes import A5
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas as pdf_canvas

        try:
            evolution = Evolution.objects.select_related(
                "patient", "doctor__user", "tenant"
            ).get(id=pk, tenant=request.tenant, type="prescription")
        except Evolution.DoesNotExist:
            raise Http404

        tenant = evolution.tenant
        buffer = io.BytesIO()
        c = pdf_canvas.Canvas(buffer, pagesize=A5)
        width, height = A5

        # ── Membrete ──
        c.setFillColorRGB(0.055, 0.353, 0.369)  # petrol
        c.rect(0, height - 26 * mm, width, 26 * mm, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 15)
        c.drawString(12 * mm, height - 12 * mm, tenant.name)
        c.setFont("Helvetica", 8)
        line2 = " · ".join(filter(None, [
            f"RUC {tenant.ruc}" if tenant.ruc else "",
            tenant.address, tenant.phone, tenant.email,
        ]))
        c.drawString(12 * mm, height - 18 * mm, line2[:95])
        c.setFont("Helvetica-Bold", 11)
        c.drawRightString(width - 12 * mm, height - 12 * mm, "RECETA")

        y = height - 36 * mm
        c.setFillColorRGB(0.09, 0.16, 0.17)

        # ── Doctor y paciente ──
        doctor = evolution.doctor
        c.setFont("Helvetica-Bold", 10)
        c.drawString(12 * mm, y, doctor.full_name if doctor else "—")
        c.setFont("Helvetica", 8)
        if doctor and doctor.license_number:
            c.drawString(12 * mm, y - 4.5 * mm, f"Reg. profesional: {doctor.license_number}")
        c.drawRightString(width - 12 * mm, y, f"Fecha: {evolution.date.strftime('%d/%m/%Y')}")

        y -= 12 * mm
        c.setFont("Helvetica", 9)
        c.drawString(12 * mm, y, f"Paciente: {evolution.patient.full_name}")
        c.drawString(12 * mm, y - 5 * mm, f"CI: {evolution.patient.national_id}")
        c.line(12 * mm, y - 9 * mm, width - 12 * mm, y - 9 * mm)

        # ── Rx ──
        y -= 18 * mm
        c.setFont("Helvetica-Bold", 16)
        c.drawString(12 * mm, y, "Rx.")
        y -= 8 * mm
        c.setFont("Helvetica", 10)
        for raw_line in evolution.notes.splitlines() or [""]:
            # partir líneas largas
            line = raw_line
            while line:
                c.drawString(16 * mm, y, line[:70])
                line = line[70:]
                y -= 6 * mm
                if y < 42 * mm:
                    break
            if y < 42 * mm:
                break

        # ── Bloque de firma ──
        # Estampar la firma manuscrita del doctor si la registró
        if doctor and doctor.signature_image:
            try:
                import base64 as _b64

                from reportlab.lib.utils import ImageReader

                _, b64data = doctor.signature_image.split(",", 1)
                sig = ImageReader(io.BytesIO(_b64.b64decode(b64data)))
                c.drawImage(sig, width / 2 - 24 * mm, 27 * mm,
                            width=48 * mm, height=16 * mm,
                            preserveAspectRatio=True, mask="auto")
            except Exception:
                pass  # firma corrupta: el PDF sale sin estampa, no falla
        c.line(width / 2 - 28 * mm, 26 * mm, width / 2 + 28 * mm, 26 * mm)
        c.setFont("Helvetica", 8)
        c.drawCentredString(width / 2, 21 * mm, doctor.full_name if doctor else "")
        c.drawCentredString(width / 2, 17 * mm, "Firma y sello")
        c.setFont("Helvetica-Oblique", 6.5)
        c.drawCentredString(
            width / 2, 9 * mm,
            f"Documento generado por {tenant.name}. Verificación: {evolution.id}",
        )

        c.showPage()
        c.save()
        buffer.seek(0)

        AuditLog.objects.create(
            tenant=request.tenant, user=request.user,
            action="print_prescription", entity_type="Evolution",
            entity_id=str(evolution.id),
            metadata={"patient_id": str(evolution.patient_id)},
        )
        return FileResponse(
            buffer, as_attachment=True,
            filename=f"receta-{evolution.patient.national_id}-{evolution.date}.pdf",
            content_type="application/pdf",
        )



class TemplateItemCreateView(APIView):
    """POST /clinical/plan-templates/{pk}/items/ — añadir tratamiento a una plantilla."""

    permission_classes = [CAN_MANAGE_TEMPLATES]

    def post(self, request, pk):
        from apps.configuration.models import Treatment

        try:
            template = TreatmentPlanTemplate.objects.get(id=pk, tenant=request.tenant)
        except TreatmentPlanTemplate.DoesNotExist:
            raise Http404
        try:
            treatment = Treatment.objects.get(id=request.data.get("treatment"), tenant=request.tenant)
        except (Treatment.DoesNotExist, ValueError, TypeError):
            return Response({"detail": "Tratamiento inválido."}, status=400)

        from apps.clinical.models import TreatmentPlanTemplateItem
        item = TreatmentPlanTemplateItem.objects.create(
            template=template, treatment=treatment,
            order=int(request.data.get("order") or (template.items.count() + 1)),
            notes=str(request.data.get("notes", ""))[:255],
        )
        return Response({"id": str(item.id), "treatment_name": treatment.name,
                         "order": item.order}, status=201)


class TemplateItemDeleteView(APIView):
    """DELETE /clinical/plan-template-items/{pk}/"""

    permission_classes = [CAN_MANAGE_TEMPLATES]

    def delete(self, request, pk):
        from apps.clinical.models import TreatmentPlanTemplateItem
        deleted, _ = TreatmentPlanTemplateItem.objects.filter(
            id=pk, template__tenant=request.tenant
        ).delete()
        if not deleted:
            raise Http404
        return Response(status=204)
