"""
Configuración (RF-CFG) — ver 04-Modelo-de-Datos, sección 9.
Sprint 2: Treatment (catálogo de tratamientos), Tariff (tarifarios),
Agreement (convenios) y SystemParameter (parámetros del sistema).
"""

from django.db import models

from apps.common.models import TenantAwareModel
from apps.specialties.models import Specialty


class Treatment(TenantAwareModel):
    """
    Catálogo de tratamientos (RF-CFG-02). Cada tratamiento pertenece a
    una especialidad y tiene un precio base. El vínculo con los insumos
    que consume (TreatmentInventoryItem) se agrega en el Sprint 11
    (Inventario), sin cambiar este modelo.
    """

    name = models.CharField(max_length=150)
    specialty = models.ForeignKey(
        Specialty, on_delete=models.PROTECT, related_name="treatments"
    )
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    consumes_inventory = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Tratamiento"
        verbose_name_plural = "Tratamientos"
        indexes = [models.Index(fields=["tenant", "specialty"])]

    def __str__(self):
        return f"{self.name} ({self.specialty.name})"


class Agreement(TenantAwareModel):
    """Convenios: aseguradoras/empresas con tarifas especiales (RF-CFG-04)."""

    name = models.CharField(max_length=150)
    discount_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Convenio"
        verbose_name_plural = "Convenios"

    def __str__(self):
        return self.name


class Tariff(TenantAwareModel):
    """
    Tarifario (RF-CFG-03): precio de un tratamiento bajo un convenio
    específico. Si no hay convenio (agreement nulo), es el tarifario
    general. Permite que un mismo tratamiento tenga precios distintos
    según la aseguradora/empresa.
    """

    treatment = models.ForeignKey(
        Treatment, on_delete=models.CASCADE, related_name="tariffs"
    )
    agreement = models.ForeignKey(
        Agreement,
        on_delete=models.CASCADE,
        related_name="tariffs",
        null=True,
        blank=True,
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Tarifario"
        verbose_name_plural = "Tarifarios"
        constraints = [
            models.UniqueConstraint(
                fields=["treatment", "agreement"],
                name="unique_tariff_per_treatment_agreement",
            )
        ]

    def __str__(self):
        target = self.agreement.name if self.agreement else "General"
        return f"{self.treatment.name} — {target}: {self.price}"


class SystemParameter(TenantAwareModel):
    """
    Parámetros del sistema (RF-CFG-05) en formato clave-valor, para que
    el admin ajuste comportamiento (días de morosidad, ventana de
    recordatorio, stock mínimo por defecto) sin cambios de código.
    """

    key = models.CharField(max_length=100)
    value = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Parámetro del sistema"
        verbose_name_plural = "Parámetros del sistema"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "key"], name="unique_parameter_key_per_tenant"
            )
        ]

    def __str__(self):
        return f"{self.key} = {self.value}"

    # Parámetros por defecto que el comando bootstrap puede sembrar.
    DEFAULTS = {
        "dias_morosidad": ("30", "Días de cuota vencida para marcar a un paciente como moroso."),
        "ventana_recordatorio_horas": ("24", "Horas antes de la cita para enviar el recordatorio por WhatsApp."),
        "stock_minimo_default": ("5", "Stock mínimo por defecto para productos nuevos de inventario."),
        "dias_alerta_vencimiento": ("30", "Días antes del vencimiento para alertar sobre un lote de inventario."),
    }


class TreatmentInventoryItem(models.Model):
    """
    Vincula un tratamiento con los insumos que consume y en qué cantidad
    (RF-INV-05). Cuando el tratamiento se marca como realizado, estos
    insumos se descuentan automáticamente del inventario.
    """

    id = models.UUIDField(primary_key=True, default=__import__("uuid").uuid4, editable=False)
    treatment = models.ForeignKey(
        Treatment, on_delete=models.CASCADE, related_name="inventory_items"
    )
    product = models.ForeignKey(
        "inventory.Product", on_delete=models.CASCADE, related_name="+"
    )
    quantity_used = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Insumo de tratamiento"
        verbose_name_plural = "Insumos de tratamiento"

    def __str__(self):
        return f"{self.treatment.name} usa {self.quantity_used} de {self.product.name}"


def _default_theme():
    return {"preset": "default", "primary": "", "secondary": ""}


class ClinicBranding(TenantAwareModel):
    """
    Identidad visual de la clínica (Sprint 33): logotipo y tema de colores.
    Un registro por tenant; cada clínica personaliza sin afectar a las demás.

    theme = {
      "preset":  "default" | nombre de tema predefinido | "auto" | "custom",
      "primary": "#rrggbb" (vacío = color del sistema),
      "secondary": "#rrggbb",
    }
    """

    logo = models.ImageField(upload_to="branding/logos/", null=True, blank=True)
    theme = models.JSONField(default=_default_theme, blank=True)
    display_name = models.CharField(
        max_length=120, blank=True, help_text="Nombre comercial de la clínica."
    )
    short_name = models.CharField(
        max_length=40, blank=True, help_text="Nombre corto (opcional, para espacios reducidos)."
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant"], name="uniq_branding_per_tenant"),
        ]

    def __str__(self):
        return f"Identidad visual de {self.tenant.name}"
