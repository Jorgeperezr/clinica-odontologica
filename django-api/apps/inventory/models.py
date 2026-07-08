"""
Inventario (RF-INV) — ver 04-Modelo-de-Datos, sección 7.
Sprint 11: Product, Batch (lotes con vencimiento), InventoryMovement.
El descuento automático al completar un tratamiento se conecta con
TreatmentPlanItem (historia clínica) y con TreatmentInventoryItem
(configuration).
"""

import uuid

from django.db import models

from apps.common.models import TenantAwareModel


class Product(TenantAwareModel):
    """Producto o insumo (RF-INV-01)."""

    name = models.CharField(max_length=150)
    unit = models.CharField(max_length=30, default="unidad", help_text="ej. unidad, ml, caja")
    min_stock = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Umbral de alerta de stock mínimo (RF-INV-03).",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"

    def __str__(self):
        return self.name

    @property
    def current_stock(self):
        """Stock total sumando todos los lotes activos."""
        return sum((b.quantity for b in self.batches.all()), start=0)

    @property
    def is_low_stock(self):
        return self.current_stock <= self.min_stock


class Batch(TenantAwareModel):
    """Lote de un producto, con fecha de vencimiento (RF-INV-02)."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="batches")
    batch_number = models.CharField(max_length=100)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    expiration_date = models.DateField(null=True, blank=True)
    received_at = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = "Lote"
        verbose_name_plural = "Lotes"
        ordering = ["expiration_date"]  # FEFO: primero el que vence antes
        indexes = [models.Index(fields=["expiration_date"])]

    def __str__(self):
        return f"{self.product.name} — lote {self.batch_number}"


class InventoryMovement(TenantAwareModel):
    """Movimiento de inventario: entrada, salida o ajuste."""

    class MovementType(models.TextChoices):
        IN = "in", "Entrada"
        OUT = "out", "Salida"

    class Reason(models.TextChoices):
        PURCHASE = "purchase", "Compra"
        CONSUMPTION = "consumption", "Consumo por tratamiento"
        ADJUSTMENT = "adjustment", "Ajuste"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="movements")
    batch = models.ForeignKey(
        Batch, on_delete=models.SET_NULL, null=True, blank=True, related_name="movements"
    )
    movement_type = models.CharField(max_length=5, choices=MovementType.choices)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=15, choices=Reason.choices)
    related_treatment_plan_item = models.ForeignKey(
        "clinical.TreatmentPlanItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimiento de inventario"
        verbose_name_plural = "Movimientos de inventario"
        ordering = ["-date"]

    def __str__(self):
        return f"{self.get_movement_type_display()} {self.quantity} {self.product.name}"
