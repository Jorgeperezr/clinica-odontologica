from decimal import Decimal

from rest_framework import serializers

from apps.billing.models import (
    Budget,
    BudgetItem,
    DoctorFee,
    Installment,
    Payment,
    PaymentPlan,
)


class BudgetItemSerializer(serializers.ModelSerializer):
    treatment_name = serializers.CharField(source="treatment.name", read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = BudgetItem
        fields = [
            "id", "treatment", "treatment_name", "tooth_fdi_code",
            "quantity", "unit_price", "subtotal",
        ]
        read_only_fields = ["id", "subtotal"]


class BudgetSerializer(serializers.ModelSerializer):
    items = BudgetItemSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Budget
        fields = [
            "id", "patient", "status", "status_display",
            "total_amount", "notes", "items", "created_at",
        ]
        read_only_fields = ["id", "created_at", "total_amount", "items", "status"]

    def validate_patient(self, value):
        if value.tenant_id != self.context["request"].tenant.id:
            raise serializers.ValidationError("El paciente no pertenece a esta clínica.")
        return value


class InstallmentSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    total_paid = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    balance = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Installment
        fields = [
            "id", "number", "due_date", "amount", "status",
            "status_display", "total_paid", "balance",
        ]
        read_only_fields = fields


class PaymentPlanSerializer(serializers.ModelSerializer):
    installments = InstallmentSerializer(many=True, read_only=True)

    class Meta:
        model = PaymentPlan
        fields = [
            "id", "budget", "patient", "total_amount",
            "installment_count", "installments", "created_at",
        ]
        read_only_fields = fields


class GeneratePaymentPlanSerializer(serializers.Serializer):
    """Body para convertir un presupuesto aprobado en plan de cuotas."""

    installment_count = serializers.IntegerField(min_value=1, max_value=60)
    first_due_date = serializers.DateField()


class PaymentSerializer(serializers.ModelSerializer):
    method_display = serializers.CharField(source="get_method_display", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id", "installment", "patient", "amount",
            "method", "method_display", "date", "created_at",
        ]
        read_only_fields = ["id", "created_at", "patient"]


class PayInstallmentSerializer(serializers.Serializer):
    """Body para registrar el pago de una cuota."""

    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    method = serializers.ChoiceField(choices=Payment.Method.choices)
    date = serializers.DateField(required=False)


class DoctorFeeSerializer(serializers.ModelSerializer):
    fee_type_display = serializers.CharField(source="get_fee_type_display", read_only=True)

    class Meta:
        model = DoctorFee
        fields = ["id", "doctor", "treatment", "fee_type", "fee_type_display", "value"]
        read_only_fields = ["id"]
