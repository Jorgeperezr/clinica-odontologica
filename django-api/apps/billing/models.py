"""
Tratamientos y pagos (RF-TRP) — ver 04-Modelo-de-Datos, sección 6.
Sprint 8: Budget, BudgetItem, PaymentPlan, Installment, Payment, DoctorFee.
El catálogo de tratamientos (Treatment) vive en configuration (Sprint 2).
El bloqueo por morosidad (RF-AGN-07) lo consume la agenda en el Sprint 9,
leyendo las cuotas vencidas de este módulo.
"""

import uuid

from django.db import models

from apps.accounts.models import User
from apps.agenda.models import Doctor
from apps.common.models import TenantAwareModel
from apps.configuration.models import Treatment
from apps.patients.models import Patient


class Budget(TenantAwareModel):
    """Presupuesto que el paciente aprueba antes de iniciar (RF-TRP-01)."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        APPROVED = "approved", "Aprobado"
        REJECTED = "rejected", "Rechazado"

    patient = models.ForeignKey(
        Patient, on_delete=models.PROTECT, related_name="budgets"
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Presupuesto"
        verbose_name_plural = "Presupuestos"

    def __str__(self):
        return f"Presupuesto {self.get_status_display()} — {self.patient} (${self.total_amount})"

    def recalculate_total(self):
        """Recalcula el total sumando los ítems. Fuente de verdad del monto."""
        total = sum((item.subtotal for item in self.items.all()), start=0)
        self.total_amount = total
        self.save(update_fields=["total_amount"])
        return total


class BudgetItem(models.Model):
    """Línea de un presupuesto (RF-TRP-01)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name="items")
    treatment = models.ForeignKey(Treatment, on_delete=models.PROTECT, related_name="+")
    tooth_fdi_code = models.CharField(max_length=2, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Ítem de presupuesto"
        verbose_name_plural = "Ítems de presupuesto"

    @property
    def subtotal(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.treatment.name} x{self.quantity}"


class PaymentPlan(TenantAwareModel):
    """Plan de pago en cuotas derivado de un presupuesto aprobado (RF-TRP-02)."""

    budget = models.OneToOneField(
        Budget, on_delete=models.PROTECT, related_name="payment_plan"
    )
    patient = models.ForeignKey(
        Patient, on_delete=models.PROTECT, related_name="payment_plans"
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    installment_count = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Plan de pago"
        verbose_name_plural = "Planes de pago"

    def __str__(self):
        return f"Plan {self.installment_count} cuotas — {self.patient}"


class Installment(TenantAwareModel):
    """Cuota individual de un plan de pago (RF-TRP-02, base de morosidad)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        PAID = "paid", "Pagada"
        OVERDUE = "overdue", "Vencida"

    payment_plan = models.ForeignKey(
        PaymentPlan, on_delete=models.CASCADE, related_name="installments"
    )
    patient = models.ForeignKey(
        Patient, on_delete=models.PROTECT, related_name="installments"
    )
    number = models.PositiveIntegerField(help_text="Número de cuota (1, 2, 3...).")
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )

    class Meta:
        verbose_name = "Cuota"
        verbose_name_plural = "Cuotas"
        ordering = ["due_date"]
        indexes = [
            models.Index(fields=["patient", "status"]),
            models.Index(fields=["due_date", "status"]),
        ]

    def __str__(self):
        return f"Cuota {self.number} — {self.patient} (${self.amount}, {self.get_status_display()})"

    @property
    def total_paid(self):
        return sum((p.amount for p in self.payments.all()), start=0)

    @property
    def balance(self):
        return self.amount - self.total_paid


class Payment(TenantAwareModel):
    """Registro de un cobro (RF-TRP-03)."""

    class Method(models.TextChoices):
        CASH = "cash", "Efectivo"
        TRANSFER = "transfer", "Transferencia"
        CARD = "card", "Tarjeta"

    installment = models.ForeignKey(
        Installment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments",
    )
    patient = models.ForeignKey(
        Patient, on_delete=models.PROTECT, related_name="payments"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=10, choices=Method.choices)
    date = models.DateField()
    registered_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"
        indexes = [models.Index(fields=["patient", "date"])]

    def __str__(self):
        return f"Pago ${self.amount} — {self.patient} ({self.date})"


class DoctorFee(TenantAwareModel):
    """Regla de cálculo de honorarios de un doctor (RF-TRP-05)."""

    class FeeType(models.TextChoices):
        PERCENTAGE = "percentage", "Porcentaje"
        FIXED = "fixed", "Monto fijo"

    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="fees")
    treatment = models.ForeignKey(
        Treatment,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
        help_text="Nulo = regla general del doctor para todos los tratamientos.",
    )
    fee_type = models.CharField(max_length=10, choices=FeeType.choices)
    value = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Honorario de doctor"
        verbose_name_plural = "Honorarios de doctores"

    def __str__(self):
        return f"{self.doctor} — {self.get_fee_type_display()}: {self.value}"
