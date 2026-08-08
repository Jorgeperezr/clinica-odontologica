from decimal import ROUND_HALF_UP, Decimal

from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing.models import (
    Budget,
    DoctorFee,
    Installment,
    Payment,
    PaymentPlan,
)
from apps.billing.serializers import (
    BudgetItemSerializer,
    BudgetSerializer,
    DoctorFeeSerializer,
    GeneratePaymentPlanSerializer,
    InstallmentSerializer,
    PayInstallmentSerializer,
    PaymentPlanSerializer,
)
from apps.common.permissions import HasRole
from apps.patients.models import Patient

CAN_MANAGE_BILLING = HasRole.for_roles("admin", "reception")
CAN_VIEW_BILLING = HasRole.for_roles("admin", "reception", "doctor")


class BudgetListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/patients/{id}/budgets/ — RF-TRP-01."""

    serializer_class = BudgetSerializer
    permission_classes = [HasRole.for_roles("admin", "reception", "doctor")]

    def get_queryset(self):
        return Budget.objects.filter(
            patient_id=self.kwargs["pk"], tenant=self.request.tenant
        ).prefetch_related("items", "items__treatment").order_by("-created_at")

    def perform_create(self, serializer):
        patient = generics.get_object_or_404(
            Patient, pk=self.kwargs["pk"], tenant=self.request.tenant, is_active=True
        )
        serializer.save(
            tenant=self.request.tenant, patient=patient, created_by=self.request.user
        )


class BudgetDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/budgets/{id}/"""

    serializer_class = BudgetSerializer
    permission_classes = [CAN_MANAGE_BILLING]

    def get_queryset(self):
        return Budget.objects.filter(tenant=self.request.tenant).prefetch_related("items")


class BudgetItemCreateView(generics.CreateAPIView):
    """POST /api/v1/budgets/{id}/items/ — agrega una línea y recalcula total."""

    serializer_class = BudgetItemSerializer
    permission_classes = [CAN_MANAGE_BILLING]

    def perform_create(self, serializer):
        budget = generics.get_object_or_404(
            Budget, pk=self.kwargs["pk"], tenant=self.request.tenant
        )
        serializer.save(budget=budget)
        budget.recalculate_total()


class BudgetApproveView(APIView):
    """POST /api/v1/budgets/{id}/approve/ — RF-TRP-01."""

    permission_classes = [CAN_MANAGE_BILLING]

    def post(self, request, pk):
        budget = generics.get_object_or_404(Budget, pk=pk, tenant=request.tenant)
        budget.status = Budget.Status.APPROVED
        budget.save(update_fields=["status"])
        return Response(BudgetSerializer(budget).data)


class GeneratePaymentPlanView(APIView):
    """
    POST /api/v1/budgets/{id}/generate-payment-plan/ — RF-TRP-02.
    Convierte un presupuesto aprobado en un plan de cuotas mensuales.
    """

    permission_classes = [CAN_MANAGE_BILLING]

    @transaction.atomic
    def post(self, request, pk):
        budget = generics.get_object_or_404(Budget, pk=pk, tenant=request.tenant)

        if budget.status != Budget.Status.APPROVED:
            return Response(
                {"detail": "El presupuesto debe estar aprobado antes de generar el plan de pago."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if hasattr(budget, "payment_plan"):
            return Response(
                {"detail": "Este presupuesto ya tiene un plan de pago."},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = GeneratePaymentPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        count = serializer.validated_data["installment_count"]
        first_due = serializer.validated_data["first_due_date"]

        plan = PaymentPlan.objects.create(
            tenant=request.tenant, budget=budget, patient=budget.patient,
            total_amount=budget.total_amount, installment_count=count,
        )

        # Repartir el total en cuotas iguales; la última absorbe el redondeo
        # para que la suma sea exactamente el total (sin centavos perdidos).
        base = (budget.total_amount / count).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        installments = []
        acumulado = Decimal("0.00")
        for i in range(1, count + 1):
            if i < count:
                amount = base
                acumulado += base
            else:
                amount = budget.total_amount - acumulado  # última cuota ajusta
            installments.append(Installment(
                tenant=request.tenant, payment_plan=plan, patient=budget.patient,
                number=i, due_date=first_due + relativedelta(months=i - 1), amount=amount,
            ))
        Installment.objects.bulk_create(installments)

        return Response(PaymentPlanSerializer(plan).data, status=status.HTTP_201_CREATED)


class PaymentPlanInstallmentsView(generics.ListAPIView):
    """GET /api/v1/payment-plans/{id}/installments/ — RF-TRP-02."""

    serializer_class = InstallmentSerializer
    permission_classes = [CAN_VIEW_BILLING]

    def get_queryset(self):
        return Installment.objects.filter(
            payment_plan_id=self.kwargs["pk"], tenant=self.request.tenant
        ).order_by("number")


class PayInstallmentView(APIView):
    """
    POST /api/v1/installments/{id}/pay/ — RF-TRP-03.
    Registra un pago sobre una cuota; si la salda, la marca como pagada.
    """

    permission_classes = [CAN_MANAGE_BILLING]

    @transaction.atomic
    def post(self, request, pk):
        installment = generics.get_object_or_404(
            Installment, pk=pk, tenant=request.tenant
        )
        serializer = PayInstallmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        amount = serializer.validated_data["amount"]
        Payment.objects.create(
            tenant=request.tenant,
            installment=installment,
            patient=installment.patient,
            amount=amount,
            method=serializer.validated_data["method"],
            date=serializer.validated_data.get("date") or timezone.now().date(),
            registered_by=request.user,
        )

        # Si el saldo llega a cero (o menos), la cuota queda pagada.
        if installment.balance <= 0:
            installment.status = Installment.Status.PAID
            installment.save(update_fields=["status"])

        return Response(InstallmentSerializer(installment).data)


class PatientAccountStatementView(APIView):
    """
    GET /api/v1/patients/{id}/account-statement/ — RF-TRP-04.
    Estado de cuenta: total, pagado, pendiente y cuotas vencidas.
    """

    permission_classes = [HasRole.for_roles("admin", "reception", "doctor")]

    def get(self, request, pk):
        patient = generics.get_object_or_404(
            Patient, pk=pk, tenant=request.tenant, is_active=True
        )
        installments = Installment.objects.filter(patient=patient, tenant=request.tenant)
        today = timezone.now().date()

        total = sum((i.amount for i in installments), start=Decimal("0.00"))
        paid = sum(
            (p.amount for p in Payment.objects.filter(patient=patient, tenant=request.tenant)),
            start=Decimal("0.00"),
        )
        overdue = [
            i for i in installments
            if i.status != Installment.Status.PAID and i.due_date < today
        ]

        return Response({
            "patient_id": str(patient.id),
            "total_amount": str(total),
            "total_paid": str(paid),
            "balance": str(total - paid),
            "overdue_count": len(overdue),
            "overdue_amount": str(sum((i.balance for i in overdue), start=Decimal("0.00"))),
        })


class DoctorFeeListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/doctors/{id}/fees/ — RF-TRP-05."""

    serializer_class = DoctorFeeSerializer
    permission_classes = [HasRole.for_roles("admin")]
    lookup_url_kwarg = "pk"

    def get_queryset(self):
        return DoctorFee.objects.filter(
            doctor_id=self.kwargs["pk"], tenant=self.request.tenant
        )

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant, doctor_id=self.kwargs["pk"])


class FinancialReportView(APIView):
    """
    GET /api/v1/reports/financial/?date_from=&date_to= — RF-TRP-06, RF-REP-01.
    Ingresos por período, desglosados por método de pago.
    """

    permission_classes = [HasRole.for_roles("admin")]

    def get(self, request):
        from django.utils.dateparse import parse_date

        payments = Payment.objects.filter(tenant=request.tenant)
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if date_from:
            payments = payments.filter(date__gte=parse_date(date_from))
        if date_to:
            payments = payments.filter(date__lte=parse_date(date_to))

        by_method = {}
        total = Decimal("0.00")
        for p in payments:
            by_method[p.method] = by_method.get(p.method, Decimal("0.00")) + p.amount
            total += p.amount

        return Response({
            "total_income": str(total),
            "by_method": {k: str(v) for k, v in by_method.items()},
            "payment_count": payments.count(),
        })


class DelinquencyReportView(APIView):
    """
    GET /api/v1/reports/delinquency/ — RF-REP-02.
    Lista de pacientes con cuotas vencidas: quién debe, cuánto y desde cuándo.
    """

    permission_classes = [HasRole.for_roles("admin", "reception")]

    def get(self, request):
        from apps.billing.services import get_delinquency_days

        threshold = get_delinquency_days(request.tenant)
        today = timezone.now().date()

        overdue = (
            Installment.objects.filter(tenant=request.tenant, due_date__lt=today)
            .exclude(status=Installment.Status.PAID)
            .select_related("patient")
        )

        by_patient = {}
        for inst in overdue:
            pid = str(inst.patient_id)
            if pid not in by_patient:
                by_patient[pid] = {
                    "patient_id": pid,
                    "patient_name": inst.patient.full_name,
                    "overdue_amount": Decimal("0.00"),
                    "oldest_due_date": inst.due_date,
                    "installment_count": 0,
                }
            entry = by_patient[pid]
            entry["overdue_amount"] += inst.balance
            entry["installment_count"] += 1
            if inst.due_date < entry["oldest_due_date"]:
                entry["oldest_due_date"] = inst.due_date

        result = []
        for entry in by_patient.values():
            days_overdue = (today - entry["oldest_due_date"]).days
            result.append({
                **entry,
                "overdue_amount": str(entry["overdue_amount"]),
                "oldest_due_date": str(entry["oldest_due_date"]),
                "days_overdue": days_overdue,
                "is_blocking": days_overdue >= threshold,
            })

        return Response({"delinquency_threshold_days": threshold, "patients": result})


class ProductionByDoctorReportView(APIView):
    """
    GET /api/v1/reports/production-by-doctor/?doctor_id= — RF-REP-03.
    Producción (citas completadas y evoluciones) por doctor.
    """

    permission_classes = [HasRole.for_roles("admin", "doctor")]

    def get(self, request):
        from apps.agenda.models import Appointment, Doctor

        doctors = Doctor.objects.filter(tenant=request.tenant, is_active=True)
        doctor_id = request.query_params.get("doctor_id")
        if doctor_id:
            doctors = doctors.filter(id=doctor_id)

        # Un doctor solo ve su propia producción
        if request.user.role == "doctor":
            doctors = doctors.filter(user=request.user)

        result = []
        for doc in doctors.select_related("user"):
            completed = Appointment.objects.filter(
                tenant=request.tenant, doctor=doc, status=Appointment.Status.COMPLETED
            ).count()
            result.append({
                "doctor_id": str(doc.id),
                "doctor_name": doc.full_name,
                "completed_appointments": completed,
            })

        return Response({"doctors": result})


class NewPatientsReportView(APIView):
    """
    GET /api/v1/reports/new-patients/?date_from=&date_to=&format=json|excel — RF-REP-04.
    """

    permission_classes = [HasRole.for_roles("admin")]

    def get(self, request):
        from django.http import HttpResponse
        from django.utils.dateparse import parse_date

        from apps.billing.report_export import build_xlsx
        from apps.patients.models import Patient

        patients = Patient.objects.filter(tenant=request.tenant, is_active=True)
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if date_from:
            patients = patients.filter(created_at__date__gte=parse_date(date_from))
        if date_to:
            patients = patients.filter(created_at__date__lte=parse_date(date_to))
        patients = patients.order_by("created_at")

        if request.query_params.get("export") == "excel":
            rows = [
                [p.full_name, p.national_id, p.phone or "", p.created_at.strftime("%Y-%m-%d")]
                for p in patients
            ]
            xlsx = build_xlsx(
                "Pacientes nuevos",
                ["Nombre", "Identificación", "Teléfono", "Fecha de registro"],
                rows,
            )
            response = HttpResponse(
                xlsx,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = 'attachment; filename="pacientes_nuevos.xlsx"'
            return response

        return Response({
            "count": patients.count(),
            "patients": [
                {"name": p.full_name, "national_id": p.national_id,
                 "registered": p.created_at.strftime("%Y-%m-%d")}
                for p in patients
            ],
        })


class InventoryReportView(APIView):
    """
    GET /api/v1/reports/inventory/?format=json|excel — RF-REP-05.
    """

    permission_classes = [HasRole.for_roles("admin", "auxiliary")]

    def get(self, request):
        from django.http import HttpResponse

        from apps.billing.report_export import build_xlsx
        from apps.inventory.models import Product

        products = Product.objects.filter(
            tenant=request.tenant, is_active=True
        ).prefetch_related("batches").order_by("name")

        if request.query_params.get("export") == "excel":
            rows = [
                [p.name, p.unit, str(p.current_stock), str(p.min_stock),
                 "SÍ" if p.is_low_stock else "NO"]
                for p in products
            ]
            xlsx = build_xlsx(
                "Inventario",
                ["Producto", "Unidad", "Stock actual", "Stock mínimo", "Stock bajo"],
                rows,
            )
            response = HttpResponse(
                xlsx,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = 'attachment; filename="inventario.xlsx"'
            return response

        return Response({
            "products": [
                {"name": p.name, "current_stock": str(p.current_stock),
                 "is_low_stock": p.is_low_stock}
                for p in products
            ],
        })


class AppointmentsSummaryReportView(APIView):
    """
    GET /api/v1/reports/appointments-summary/?date_from=&date_to= — Sprint 31.
    Actividad de citas del período: totales por estado, tasa de asistencia
    (completadas frente a completadas + no asistió) y tasa de cancelación.
    """

    permission_classes = [HasRole.for_roles("admin")]

    def get(self, request):
        from django.utils.dateparse import parse_date

        from apps.agenda.models import Appointment

        appts = Appointment.objects.filter(tenant=request.tenant)
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if date_from:
            appts = appts.filter(scheduled_start__date__gte=parse_date(date_from))
        if date_to:
            appts = appts.filter(scheduled_start__date__lte=parse_date(date_to))

        by_status = {}
        for a in appts.values_list("status", flat=True):
            by_status[a] = by_status.get(a, 0) + 1

        completed = by_status.get("completed", 0)
        no_show = by_status.get("no_show", 0)
        cancelled = by_status.get("cancelled", 0)
        total = sum(by_status.values())
        attended_universe = completed + no_show

        return Response({
            "total": total,
            "by_status": by_status,
            "attendance_rate": round(completed / attended_universe * 100, 1) if attended_universe else None,
            "cancellation_rate": round(cancelled / total * 100, 1) if total else None,
        })


class PatientPaymentListCreateView(generics.ListCreateAPIView):
    """
    GET/POST /api/v1/patients/{pk}/payments/ — Sprint 45.
    Cobros del paciente y registro directo desde su ficha, sin cambiar de
    módulo. El pago queda sin cuota asociada (`installment=null`), que el
    modelo ya contempla; los abonos a un plan siguen usando su endpoint.
    """

    permission_classes = [HasRole.for_roles("admin", "reception")]

    def get_serializer_class(self):
        from apps.billing.serializers import PaymentSerializer
        return PaymentSerializer

    def get_queryset(self):
        return Payment.objects.filter(
            tenant=self.request.tenant, patient_id=self.kwargs["pk"]
        ).order_by("-date", "-created_at")

    def perform_create(self, serializer):
        patient = generics.get_object_or_404(
            Patient, pk=self.kwargs["pk"], tenant=self.request.tenant
        )
        serializer.save(
            tenant=self.request.tenant, patient=patient,
            registered_by=self.request.user,
        )


class BirthdaysView(APIView):
    """
    GET /api/v1/patients/birthdays/?days=7 — Sprint 45.
    Pacientes que cumplen años hoy y en los próximos días, para recordarlo
    desde el panel de inicio y desde recepción. Compara mes y día, así que
    funciona igual en cualquier año.
    """

    permission_classes = [HasRole.for_roles("admin", "reception", "doctor", "auxiliary")]

    def get(self, request):
        from datetime import date, timedelta

        try:
            days = max(0, min(int(request.query_params.get("days", 7)), 60))
        except ValueError:
            days = 7

        today = date.today()
        # Pares (mes, día) de la ventana consultada
        wanted = {}
        for offset in range(days + 1):
            d = today + timedelta(days=offset)
            wanted.setdefault((d.month, d.day), offset)

        qs = Patient.objects.filter(
            tenant=request.tenant, is_active=True, birth_date__isnull=False
        ).only("id", "first_name", "last_name", "birth_date", "phone")

        results = []
        for p in qs:
            key = (p.birth_date.month, p.birth_date.day)
            if key not in wanted:
                continue
            offset = wanted[key]
            turns = today.year - p.birth_date.year
            if (today.month, today.day) < key:
                turns = today.year - p.birth_date.year
            results.append({
                "id": str(p.id),
                "full_name": f"{p.first_name} {p.last_name}",
                "phone": p.phone,
                "birth_date": p.birth_date.isoformat(),
                "in_days": offset,
                "is_today": offset == 0,
                "turns": turns,
            })
        results.sort(key=lambda r: (r["in_days"], r["full_name"]))
        return Response(results)
