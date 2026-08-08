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
    address = models.CharField(max_length=200, blank=True, help_text="Dirección de la clínica.")
    phone = models.CharField(max_length=40, blank=True, help_text="Teléfono de contacto.")
    email = models.EmailField(blank=True, help_text="Correo electrónico institucional.")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant"], name="uniq_branding_per_tenant"),
        ]

    def __str__(self):
        return f"Identidad visual de {self.tenant.name}"


# ── Apariencia de documentos (Sprint 60) ─────────────────────────────
#
# Motor global de estilos: TODOS los documentos clínicos y administrativos
# (recetas, consentimientos, solicitudes, informes, presupuestos, planes,
# certificados, reportes…) leen su apariencia de aquí en vez de llevar
# colores, tipografías y márgenes escritos a mano en cada generador.
#
# ÚNICA EXCEPCIÓN: el formulario MSP HCU-033/2021. Es un formato oficial
# del Ministerio con un diseño legalmente fijado; personalizarlo lo
# invalidaría, así que conserva su generador propio.
#
# Los ajustes se guardan agrupados en JSON, no en sesenta columnas. Dos
# razones: la tabla no crece con cada preferencia nueva, y —lo que de
# verdad importa— un documento futuro puede añadir sus propios ajustes sin
# migración, que es el requisito de que el sistema absorba documentos
# nuevos automáticamente. Cada grupo tiene su función de valores por
# defecto (con nombre, no lambda: las migraciones deben poder importarla).

def _default_doc_header():
    return {
        "enabled": True,
        "show_logo": True, "show_clinic_name": True, "show_professional": True,
        "show_specialty": True, "show_address": True, "show_phone": True,
        "show_email": True, "show_website": False,
        "align": "left",            # left | center | right
        "height_mm": 26,
        "background": "", "text_color": "",   # vacío = usa la paleta
    }


def _default_doc_footer():
    return {
        "enabled": True,
        "text": "", "show_page_numbers": True, "show_date": True,
        "show_time": False, "show_clinic": True, "legal_text": "",
        "align": "center", "text_color": "",
    }


def _default_doc_typography():
    return {
        "family": "Helvetica",      # familia base de reportlab
        "size_pt": 10, "weight": "normal",
        "letter_spacing": 0, "line_height": 1.35,
        "color": "#1f2937",
        "title_size_pt": 16, "subtitle_size_pt": 12,
    }


def _default_doc_palette():
    return {
        # Vacío en `primary` = hereda el color de marca de la clínica
        "primary": "", "secondary": "#6b7280", "accent": "#0e5c63",
        "title": "#111827", "subtitle": "#374151",
        "table_header_bg": "#0e5c63", "table_header_text": "#ffffff",
        "icon": "#0e5c63", "highlight": "#fef3c7", "alert": "#b91c1c",
        "separator": "#d1d5db",
    }


def _default_doc_tables():
    return {
        "header_bg": "", "border_color": "", "border_width": 0.6,
        "rounded": False, "shaded": True, "zebra": True,
        "zebra_color": "#f9fafb", "cell_padding_mm": 2, "row_spacing_mm": 0,
    }


def _default_doc_page():
    return {
        "size": "A4",               # A4 | LETTER | LEGAL
        "orientation": "portrait",  # portrait | landscape
        "margin_top_mm": 20, "margin_bottom_mm": 18,
        "margin_left_mm": 20, "margin_right_mm": 20,
        "columns": 1, "block_spacing_mm": 5,
    }


def _default_doc_logo():
    return {
        "position": "header_left",  # header_left | header_center | header_right
        "width_mm": 26, "height_mm": 20, "opacity": 1.0, "gap_mm": 4,
    }


def _default_doc_signature():
    return {
        "show_image": True, "show_name": True, "show_license": True,
        "show_specialty": True,
        "position": "right",        # left | center | right
        "width_mm": 45, "height_mm": 18,
    }


def _default_doc_watermark():
    return {
        "enabled": False, "text": "", "opacity": 0.08,
        "position": "center", "size_pt": 60, "rotation": 45,
    }


class DocumentAppearance(TenantAwareModel):
    """
    Apariencia de los documentos de una clínica. Un registro por tenant.
    Lo consume `apps.common.document_style`, que es el único punto por el
    que los generadores obtienen colores, tipografías y medidas.
    """

    header = models.JSONField(default=_default_doc_header, blank=True)
    footer = models.JSONField(default=_default_doc_footer, blank=True)
    typography = models.JSONField(default=_default_doc_typography, blank=True)
    palette = models.JSONField(default=_default_doc_palette, blank=True)
    tables = models.JSONField(default=_default_doc_tables, blank=True)
    page = models.JSONField(default=_default_doc_page, blank=True)
    logo = models.JSONField(default=_default_doc_logo, blank=True)
    signature = models.JSONField(default=_default_doc_signature, blank=True)
    watermark = models.JSONField(default=_default_doc_watermark, blank=True)

    class Meta:
        verbose_name = "Apariencia de documentos"
        verbose_name_plural = "Apariencia de documentos"
        constraints = [
            models.UniqueConstraint(fields=["tenant"], name="uniq_docappearance_per_tenant"),
        ]

    def __str__(self):
        return f"Apariencia de documentos de {self.tenant.name}"

    # Grupos que componen la apariencia, en orden de presentación.
    GROUPS = (
        "header", "footer", "typography", "palette",
        "tables", "page", "logo", "signature", "watermark",
    )

    DEFAULTS = {
        "header": _default_doc_header, "footer": _default_doc_footer,
        "typography": _default_doc_typography, "palette": _default_doc_palette,
        "tables": _default_doc_tables, "page": _default_doc_page,
        "logo": _default_doc_logo, "signature": _default_doc_signature,
        "watermark": _default_doc_watermark,
    }

    def resolved(self):
        """
        Ajustes completos, rellenando con los valores por defecto las
        claves ausentes. Es lo que da compatibilidad hacia atrás: un
        registro guardado antes de que existiera un ajuste nuevo sigue
        siendo válido y el ajuste nuevo aparece con su valor por defecto,
        sin migración de datos.
        """
        out = {}
        for group in self.GROUPS:
            base = self.DEFAULTS[group]()
            base.update(getattr(self, group) or {})
            out[group] = base
        return out
