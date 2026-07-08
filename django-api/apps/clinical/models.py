"""
Historia clínica (RF-HCL) — ver 04-Modelo-de-Datos, sección 4.
Sprint 4: ClinicalRecord, Evolution (con type y visible_to_patient),
Diagnosis, TreatmentPlan y TreatmentPlanItem.
El odontograma (OdontogramState, ToothRecord) y consentimientos/
radiografías van en los Sprints 5-6.
"""

import uuid

from django.db import models

from apps.accounts.models import User
from apps.agenda.models import Doctor
from apps.common.models import TenantAwareModel
from apps.patients.models import Patient


class ClinicalRecord(models.Model):
    """Historia clínica general, uno a uno con el paciente (RF-HCL-01)."""

    patient = models.OneToOneField(
        Patient, on_delete=models.CASCADE, related_name="clinical_record"
    )
    general_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Historia clínica"
        verbose_name_plural = "Historias clínicas"

    def __str__(self):
        return f"HC de {self.patient}"


class Evolution(TenantAwareModel):
    """
    Nota clínica fechada por cita (RF-HCL-03). El campo 'type' (aprobado
    en la adenda de la Fase 5) permite que una misma tabla represente
    notas clínicas, recetas e indicaciones de cuidado — estas dos últimas
    son las que la app móvil muestra al paciente (RF-APP-04, RF-APP-06).
    """

    class Type(models.TextChoices):
        CLINICAL_NOTE = "clinical_note", "Nota clínica"
        PRESCRIPTION = "prescription", "Receta"
        CARE_INSTRUCTION = "care_instruction", "Indicación de cuidado"

    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name="evolutions"
    )
    doctor = models.ForeignKey(
        Doctor, on_delete=models.PROTECT, related_name="evolutions",
        null=True, blank=True,
        help_text="Nulo si registró un usuario clínico sin perfil de doctor (admin/auxiliar).",
    )
    appointment = models.ForeignKey(
        "agenda.Appointment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evolutions",
    )
    type = models.CharField(
        max_length=20, choices=Type.choices, default=Type.CLINICAL_NOTE
    )
    date = models.DateField()
    notes = models.TextField()
    visible_to_patient = models.BooleanField(
        default=False,
        help_text="Si es True, el paciente lo ve en la app (RF-APP-03).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Evolución"
        verbose_name_plural = "Evoluciones"
        indexes = [
            models.Index(fields=["patient", "date"]),
            models.Index(fields=["patient", "type", "visible_to_patient"]),
        ]

    def __str__(self):
        return f"{self.get_type_display()} — {self.patient} ({self.date})"


class Diagnosis(TenantAwareModel):
    """Diagnóstico asociado a una pieza o general (RF-HCL-04)."""

    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name="diagnoses"
    )
    doctor = models.ForeignKey(
        Doctor, on_delete=models.PROTECT, related_name="diagnoses",
        null=True, blank=True,
    )
    tooth_fdi_code = models.CharField(
        max_length=2, blank=True,
        help_text="Código FDI (ej. '26'); vacío si es diagnóstico general.",
    )
    code = models.CharField(max_length=20, blank=True)
    description = models.TextField()
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Diagnóstico"
        verbose_name_plural = "Diagnósticos"

    def __str__(self):
        target = f"pieza {self.tooth_fdi_code}" if self.tooth_fdi_code else "general"
        return f"Dx {target} — {self.patient}"


class TreatmentPlan(TenantAwareModel):
    """Plan de tratamiento: secuencia de procedimientos (RF-HCL-05)."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        ACTIVE = "active", "Activo"
        COMPLETED = "completed", "Completado"

    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name="treatment_plans"
    )
    created_by = models.ForeignKey(
        Doctor, on_delete=models.PROTECT, related_name="treatment_plans",
        null=True, blank=True,
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Plan de tratamiento"
        verbose_name_plural = "Planes de tratamiento"

    def __str__(self):
        return f"Plan {self.get_status_display()} — {self.patient}"


class TreatmentPlanItem(models.Model):
    """Procedimiento individual dentro de un plan (RF-HCL-05)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Status(models.TextChoices):
        PLANNED = "planned", "Planificado"
        IN_PROGRESS = "in_progress", "En progreso"
        DONE = "done", "Realizado"

    treatment_plan = models.ForeignKey(
        TreatmentPlan, on_delete=models.CASCADE, related_name="items"
    )
    treatment = models.ForeignKey(
        "configuration.Treatment", on_delete=models.PROTECT, related_name="+"
    )
    tooth_fdi_code = models.CharField(max_length=2, blank=True)
    order = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.PLANNED
    )
    estimated_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Ítem de plan de tratamiento"
        verbose_name_plural = "Ítems de plan de tratamiento"
        ordering = ["order"]

    def __str__(self):
        return f"{self.treatment.name} ({self.get_status_display()})"


class OdontogramState(TenantAwareModel):
    """
    Catálogo de estados de una pieza dental (SRS, sección 3.4.1).
    Basado en notación FDI/ISO 3950. Parametrizable: el admin/doctor
    puede editar los estados sin tocar código. Los 12 estados base se
    siembran por el comando bootstrap.
    """

    code = models.CharField(max_length=30)
    label = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default="#000000", help_text="Color hex para la UI.")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Estado de odontograma"
        verbose_name_plural = "Estados de odontograma"
        ordering = ["order", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "code"], name="unique_odontogram_state_code_per_tenant"
            )
        ]

    def __str__(self):
        return f"{self.code} — {self.label}"

    # Catálogo base sembrado por bootstrap (SRS 3.4.1). Formato:
    # code: (label, color, order)
    DEFAULTS = {
        "SANO": ("Sano", "#ffffff", 1),
        "CARIES": ("Caries activa", "#dc2626", 2),
        "OBTURADO": ("Obturado / restauración", "#2563eb", 3),
        "CORONA": ("Corona protésica", "#eab308", 4),
        "AUSENTE": ("Ausente", "#111827", 5),
        "INDICADA_EXTRACCION": ("Indicada para extracción", "#f97316", 6),
        "ENDODONCIA": ("Endodoncia realizada", "#7c3aed", 7),
        "IMPLANTE": ("Implante", "#0891b2", 8),
        "FRACTURA": ("Fractura", "#be123c", 9),
        "PROTESIS_REMOVIBLE": ("Prótesis removible", "#6b7280", 10),
        "SELLANTE": ("Sellante", "#16a34a", 11),
        "EN_TRATAMIENTO": ("En tratamiento (planificado)", "#94a3b8", 12),
    }


class ToothRecord(TenantAwareModel):
    """
    Registro histórico del estado de una pieza dental por superficie
    (RF-HCL-02). NUNCA se actualiza un registro existente: cada cambio
    crea una fila nueva, formando el historial. El "estado actual" de una
    pieza es el registro más reciente por (pieza, superficie).
    """

    class Surface(models.TextChoices):
        WHOLE = "whole", "Toda la pieza"
        VESTIBULAR = "vestibular", "Vestibular"
        PALATAL_LINGUAL = "palatal_lingual", "Palatina/Lingual"
        MESIAL = "mesial", "Mesial"
        DISTAL = "distal", "Distal"
        OCCLUSAL = "occlusal", "Oclusal"

    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name="tooth_records"
    )
    tooth_fdi_code = models.CharField(
        max_length=2, help_text="Código FDI: 11-48 (permanente), 51-85 (temporal)."
    )
    surface = models.CharField(
        max_length=20, choices=Surface.choices, default=Surface.WHOLE
    )
    state = models.ForeignKey(
        OdontogramState, on_delete=models.PROTECT, related_name="tooth_records"
    )
    doctor = models.ForeignKey(
        Doctor, on_delete=models.PROTECT, related_name="tooth_records",
        null=True, blank=True,
    )
    treatment_plan_item = models.ForeignKey(
        TreatmentPlanItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tooth_records",
    )
    date = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro de pieza dental"
        verbose_name_plural = "Registros de piezas dentales"
        indexes = [
            models.Index(fields=["patient", "tooth_fdi_code", "surface"]),
            models.Index(fields=["patient", "-created_at"]),
        ]

    def __str__(self):
        return f"Pieza {self.tooth_fdi_code} ({self.surface}) — {self.state.code}"


class RadiographPhoto(TenantAwareModel):
    """Radiografía o fotografía clínica (RF-HCL-06)."""

    class Type(models.TextChoices):
        RADIOGRAPH = "radiograph", "Radiografía"
        PHOTO = "photo", "Fotografía"

    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name="radiographs"
    )
    tooth_fdi_code = models.CharField(max_length=2, blank=True)
    file = models.FileField(upload_to="clinical/radiographs/")
    type = models.CharField(max_length=15, choices=Type.choices, default=Type.RADIOGRAPH)
    description = models.CharField(max_length=255, blank=True)
    date = models.DateField()
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Radiografía / Fotografía"
        verbose_name_plural = "Radiografías / Fotografías"

    def __str__(self):
        return f"{self.get_type_display()} — {self.patient} ({self.date})"


class InformedConsent(TenantAwareModel):
    """
    Consentimiento informado firmado en pantalla táctil (RF-HCL-07).
    Para Ecuador se usa como REGISTRO INTERNO (sin firma electrónica
    calificada): se guarda la imagen de la firma incrustada en un PDF
    y se registra fecha/hora/IP como evidencia del acto.
    """

    patient = models.ForeignKey(
        Patient, on_delete=models.PROTECT, related_name="consents"
    )
    treatment_plan = models.ForeignKey(
        TreatmentPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consents",
    )
    title = models.CharField(max_length=200, default="Consentimiento informado")
    body_text = models.TextField(
        help_text="Texto del consentimiento que el paciente acepta."
    )
    pdf_file = models.FileField(upload_to="clinical/consents/", null=True, blank=True)
    signature_image = models.ImageField(
        upload_to="clinical/signatures/", null=True, blank=True
    )
    signed_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_info = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Consentimiento informado"
        verbose_name_plural = "Consentimientos informados"

    def __str__(self):
        estado = "firmado" if self.signed_at else "pendiente"
        return f"{self.title} — {self.patient} ({estado})"

    @property
    def is_signed(self):
        return self.signed_at is not None
