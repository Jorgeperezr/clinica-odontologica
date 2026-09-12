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
from apps.configuration.pricing import prefetch_tariffs, price_for

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


def _item_price(item, agreement, tariffs):
    """
    Precio de una línea del plan al pasarla a presupuesto.

    Un `estimated_price` escrito a mano manda sobre el tarifario: si el
    odontólogo pactó una cifra con el paciente, el convenio no debe
    reescribirla por la espalda. Lo que sí se sustituye es el valor que el
    propio sistema puso por defecto —vacío, o copiado del precio base al
    aplicar una plantilla—, porque eso no lo decidió nadie.
    """
    estimated = item.estimated_price
    auto = not estimated or estimated == item.treatment.base_price
    if auto:
        return price_for(item.treatment, agreement, tariffs=tariffs)
    return estimated


class PlanToBudgetView(APIView):
    """
    POST /api/v1/treatment-plans/{pk}/generate-budget/
    Presupuesto automático: crea el Budget (billing) con un ítem por cada
    ítem del plan, a la tarifa que corresponde al convenio del paciente.
    Une el flujo clínico con el financiero en un clic.
    """

    permission_classes = [HasRole.for_roles("admin", "reception", "doctor")]

    def post(self, request, pk):
        from apps.billing.models import Budget, BudgetItem
        from apps.billing.serializers import BudgetSerializer

        try:
            plan = (
                TreatmentPlan.objects
                .select_related("patient__agreement")
                .prefetch_related("items__treatment")
                .get(id=pk, tenant=request.tenant)
            )
        except TreatmentPlan.DoesNotExist:
            return Response({"detail": "Plan no encontrado."}, status=404)

        items = list(plan.items.all())
        if not items:
            return Response({"detail": "El plan no tiene ítems."}, status=400)

        # El presupuesto se emite con la tarifa del convenio del paciente
        # (Sprint 71). Antes se usaba siempre el precio base del catálogo:
        # la clínica podía tener cargado el tarifario entero de una
        # aseguradora y seguir presupuestando la tarifa particular.
        agreement = plan.patient.agreement
        tariffs = prefetch_tariffs(request.tenant, agreement)

        budget = Budget.objects.create(
            tenant=request.tenant, patient=plan.patient,
            notes="Generado automáticamente desde el plan de tratamiento.",
        )
        total = 0
        for item in items:
            price = _item_price(item, agreement, tariffs)
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
            metadata={
                "plan_id": str(plan.id), "total": str(total),
                "agreement": agreement.name if agreement else None,
            },
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
    GET /api/v1/evolutions/{pk}/prescription-pdf/ — receta profesional.

    La vista resuelve los datos; el dibujo lo hace
    `apps.clinical.prescription_pdf` con la apariencia configurada por la
    clínica, igual que el resto de documentos (Sprint 64).
    """

    permission_classes = [CAN_VIEW_CLINICAL]

    def get(self, request, pk):
        from apps.clinical.prescription_pdf import build_prescription_pdf
        from apps.common.document_style import clinic_snapshot, get_document_style

        try:
            evolution = Evolution.objects.select_related(
                "patient", "doctor__user", "tenant"
            ).get(id=pk, tenant=request.tenant, type="prescription")
        except Evolution.DoesNotExist:
            raise Http404

        doctor = evolution.doctor
        specialty = ""
        if doctor:
            specialty = ", ".join(s.name for s in doctor.specialties.all()) or ""

        pdf_bytes = build_prescription_pdf(
            clinic=clinic_snapshot(request.tenant),
            professional={
                "full_name": doctor.full_name if doctor else "",
                "specialty": specialty,
                "license_number": doctor.license_number if doctor else "",
                "signature_b64": doctor.signature_image if doctor else None,
            },
            patient={
                "full_name": evolution.patient.full_name,
                "national_id": evolution.patient.national_id,
            },
            prescription={
                "date": evolution.date.strftime("%d/%m/%Y"),
                "notes": evolution.notes,
                "reference": str(evolution.id),
            },
            style=get_document_style(request.tenant),
        )

        AuditLog.objects.create(
            tenant=request.tenant, user=request.user,
            action="print_prescription", entity_type="Evolution",
            entity_id=str(evolution.id),
            metadata={"patient_id": str(evolution.patient_id)},
        )
        return FileResponse(
            io.BytesIO(pdf_bytes), as_attachment=True,
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
