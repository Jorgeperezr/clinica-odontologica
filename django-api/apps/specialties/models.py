"""
Especialidades (RF-ESP) — ver 04-Modelo-de-Datos, sección 5.
Sprint 2: el catálogo de Specialty (base para tratamientos y agenda).
Los formularios clínicos por especialidad (SpecialtyForm) se implementan
en el Sprint 7, cuando exista la historia clínica.
"""

from django.db import models

from apps.common.models import TenantAwareModel


class Specialty(TenantAwareModel):
    """
    Catálogo de especialidades odontológicas (RF-CFG-01).
    Las 5 base del SRS: Clínica general, Ortodoncia, Endodoncia,
    Periodoncia, Odontopediatría. Es ABM: el admin puede agregar más.
    """

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Especialidad"
        verbose_name_plural = "Especialidades"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"], name="unique_specialty_name_per_tenant"
            )
        ]

    def __str__(self):
        return self.name


class SpecialtyForm(TenantAwareModel):
    """
    Formulario clínico específico por especialidad (RF-ESP-01, RF-ESP-02).
    Usa un JSONField para los datos, de modo que cada especialidad puede
    definir sus propios campos sin requerir migraciones ni cambios de
    código cuando el doctor ajuste qué se registra. La validación de qué
    campos aplican a cada especialidad se hace por serializer/plantilla.
    """

    specialty = models.ForeignKey(
        Specialty, on_delete=models.PROTECT, related_name="forms"
    )
    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.CASCADE, related_name="specialty_forms"
    )
    doctor = models.ForeignKey(
        "agenda.Doctor", on_delete=models.PROTECT, related_name="specialty_forms"
    )
    date = models.DateField()
    form_data = models.JSONField(
        default=dict,
        help_text="Campos específicos de la especialidad (estructura flexible).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Formulario de especialidad"
        verbose_name_plural = "Formularios de especialidad"
        indexes = [models.Index(fields=["patient", "specialty"])]

    def __str__(self):
        return f"{self.specialty.name} — {self.patient} ({self.date})"


# Plantillas base de campos por especialidad. Sirven como sugerencia para
# el frontend (qué campos mostrar) y como referencia de validación. El
# doctor puede ajustarlas; no están "grabadas en piedra" en el esquema.
SPECIALTY_FORM_TEMPLATES = {
    "Ortodoncia": [
        {"key": "tipo_aparato", "label": "Tipo de aparato", "type": "text"},
        {"key": "fase_tratamiento", "label": "Fase del tratamiento", "type": "text"},
        {"key": "meses_estimados", "label": "Duración estimada (meses)", "type": "number"},
        {"key": "clasificacion_angle", "label": "Clasificación de Angle", "type": "text"},
    ],
    "Endodoncia": [
        {"key": "pieza_tratada", "label": "Pieza tratada (FDI)", "type": "text"},
        {"key": "numero_conductos", "label": "Número de conductos", "type": "number"},
        {"key": "longitud_trabajo", "label": "Longitud de trabajo (mm)", "type": "number"},
        {"key": "vitalidad_pulpar", "label": "Vitalidad pulpar", "type": "text"},
    ],
    "Periodoncia": [
        {"key": "profundidad_bolsa", "label": "Profundidad de bolsa (mm)", "type": "number"},
        {"key": "sangrado_sondaje", "label": "Sangrado al sondaje", "type": "boolean"},
        {"key": "movilidad_dental", "label": "Movilidad dental (grado)", "type": "number"},
        {"key": "indice_placa", "label": "Índice de placa (%)", "type": "number"},
    ],
    "Odontopediatría": [
        {"key": "edad_dental", "label": "Edad dental", "type": "text"},
        {"key": "comportamiento", "label": "Comportamiento (escala Frankl)", "type": "text"},
        {"key": "denticion", "label": "Tipo de dentición", "type": "text"},
        {"key": "necesita_sedacion", "label": "Requiere sedación", "type": "boolean"},
    ],
}
