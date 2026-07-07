from decimal import Decimal, ROUND_HALF_UP

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
