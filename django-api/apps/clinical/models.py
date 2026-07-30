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
    follow_up_date = models.DateField(
        null=True, blank=True,
        help_text="Fecha de seguimiento: genera una alerta cuando llega (Sprint 22).",
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="Usuario que registró la evolución (doctor, admin o auxiliar).",
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
    code = models.CharField(max_length=20, blank=True, help_text="Código CIE-10.")
    description = models.TextField()
    diagnosis_kind = models.CharField(
        max_length=3,
        choices=[("pre", "Presuntivo"), ("def", "Definitivo")],
        default="pre",
        help_text="PRE/DEF según formulario MSP 033.",
    )
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
        # Simbología HCU-form.033/2021 (literal K):
        # ROJO = patología actual / indicado; AZUL = tratamiento realizado.
        "SANO": ("Sano", "#ffffff", 1),
        "CARIES": ("Caries", "#c62828", 2),
        "OBTURADO": ("Obturado", "#1565c0", 3),
        "SELLANTE_NECESARIO": ("Sellante necesario", "#c62828", 4),
        "SELLANTE": ("Sellante realizado", "#1565c0", 5),
        "INDICADA_EXTRACCION": ("Extracción indicada", "#c62828", 6),
        "PERDIDA_CARIES": ("Pérdida por caries", "#1565c0", 7),
        "PERDIDA_OTRA": ("Pérdida (otra causa)", "#111827", 8),
        "AUSENTE": ("Ausente", "#111827", 9),
        "ENDODONCIA_INDICADA": ("Endodoncia por realizar", "#c62828", 10),
        "ENDODONCIA": ("Endodoncia realizada", "#1565c0", 11),
        "CORONA_INDICADA": ("Corona indicada", "#c62828", 12),
        "CORONA": ("Corona realizada", "#1565c0", 13),
        "PROTESIS_FIJA_INDICADA": ("Prótesis fija indicada", "#c62828", 14),
        "PROTESIS_FIJA": ("Prótesis fija realizada", "#1565c0", 15),
        "PROTESIS_REMOVIBLE_INDICADA": ("Prótesis removible indicada", "#c62828", 16),
        "PROTESIS_REMOVIBLE": ("Prótesis removible realizada", "#1565c0", 17),
        "PROTESIS_TOTAL_INDICADA": ("Prótesis total indicada", "#c62828", 18),
        "PROTESIS_TOTAL": ("Prótesis total realizada", "#1565c0", 19),
        "IMPLANTE": ("Implante", "#0891b2", 20),
        "FRACTURA": ("Fractura", "#7f1d1d", 21),
        "EN_TRATAMIENTO": ("En tratamiento (planificado)", "#94a3b8", 22),
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
    mobility = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Movilidad 1-4 (formulario MSP 033)."
    )
    recession = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Recesión 1-4 (formulario MSP 033)."
    )
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
    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        PENDING = "pending", "Pendiente de firma"
        SIGNED = "signed", "Firmado"
        VOID = "void", "Anulado"

    title = models.CharField(max_length=200, default="Consentimiento informado")
    body_text = models.TextField(
        help_text="Texto del consentimiento que el paciente acepta."
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    # Secciones estructuradas del documento (opcionales; body_text sigue
    # sirviendo como descripción/base para consentimientos antiguos).
    procedure = models.TextField(blank=True, help_text="Descripción del procedimiento.")
    benefits = models.TextField(blank=True, help_text="Beneficios.")
    risks = models.TextField(blank=True, help_text="Riesgos y posibles complicaciones.")
    alternatives = models.TextField(blank=True, help_text="Alternativas terapéuticas.")
    observations = models.TextField(blank=True, help_text="Observaciones (opcional).")
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


class TreatmentPlanTemplate(TenantAwareModel):
    """
    Plantilla de plan de tratamiento (Sprint 22): protocolos reutilizables
    (ej. "Ortodoncia completa", "Rehabilitación superior") que al aplicarse
    a un paciente crean el plan con todos sus ítems y precios del tarifario.
    """

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Plantilla de plan de tratamiento"
        verbose_name_plural = "Plantillas de planes de tratamiento"
        unique_together = [("tenant", "name")]

    def __str__(self):
        return self.name


class TreatmentPlanTemplateItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        TreatmentPlanTemplate, on_delete=models.CASCADE, related_name="items"
    )
    treatment = models.ForeignKey(
        "configuration.Treatment", on_delete=models.PROTECT, related_name="+"
    )
    order = models.PositiveIntegerField(default=1)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["order"]



class Cie10(models.Model):
    """Catálogo CIE-10 (global, sin tenant) para el literal N del 033."""

    code = models.CharField(max_length=10, unique=True)
    description = models.CharField(max_length=255)

    class Meta:
        verbose_name = "Código CIE-10"
        verbose_name_plural = "Códigos CIE-10"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.description}"


class Form033Record(TenantAwareModel):
    """
    Historia Clínica Odontológica — formulario MSP HCU-form.033/2021.
    Secciones B-G e I por consulta. La sección A (establecimiento/paciente)
    vive en Tenant/Patient; H (odontograma) en ToothRecord; N en Diagnosis;
    O se guarda AUTOMÁTICAMENTE en professional_snapshot; P en TreatmentPlan.
    """

    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.CASCADE, related_name="form033_records"
    )
    # B / C
    motivo_consulta = models.TextField(blank=True)
    embarazada = models.BooleanField(null=True, blank=True)
    enfermedad_actual = models.TextField(blank=True)
    # D / E — checkboxes del formulario + detalle libre
    antecedentes_personales = models.JSONField(default=dict, blank=True)
    antecedentes_familiares = models.JSONField(default=dict, blank=True)
    # F
    temperatura = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    pulso = models.PositiveSmallIntegerField(null=True, blank=True)
    frecuencia_respiratoria = models.PositiveSmallIntegerField(null=True, blank=True)
    presion_arterial = models.CharField(max_length=15, blank=True)
    # G — regiones con patología descrita
    examen_estomatognatico = models.JSONField(default=dict, blank=True)
    # I — indicadores de salud bucal
    indicadores_salud_bucal = models.JSONField(default=dict, blank=True)
    # O — se llena SOLO desde la credencial del profesional autenticado
    doctor = models.ForeignKey(
        "agenda.Doctor", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="+")
    professional_snapshot = models.JSONField(default=dict, blank=True)
    date = models.DateField()

    class Meta:
        verbose_name = "Historia odontológica (Form 033)"
        verbose_name_plural = "Historias odontológicas (Form 033)"
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"Form033 {self.date} — {self.patient}"


class ExamRequest(TenantAwareModel):
    """Literales L (pedido de exámenes) y M (informe) del formulario 033."""

    class Category(models.TextChoices):
        BIOMETRIA = "biometria", "Biometría"
        QUIMICA = "quimica_sanguinea", "Química sanguínea"
        RAYOS_X = "rayos_x", "Rayos X"
        OTROS = "otros", "Otros"

    class Status(models.TextChoices):
        PENDING = "pending", "Pedido"
        REPORTED = "reported", "Con informe"

    class Priority(models.TextChoices):
        NORMAL = "normal", "Normal"
        URGENT = "urgent", "Urgente"

    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.CASCADE, related_name="exam_requests"
    )
    category = models.CharField(max_length=20, choices=Category.choices)
    detail = models.CharField(max_length=255, help_text="Examen solicitado.")
    justification = models.TextField(blank=True, help_text="Motivo o justificación clínica.")
    observations = models.TextField(blank=True, help_text="Observaciones adicionales (opcional).")
    priority = models.CharField(
        max_length=10, choices=Priority.choices, default=Priority.NORMAL
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    report_notes = models.TextField(blank=True, help_text="M. Informe de exámenes.")
    report_document = models.ForeignKey(
        "patients.PatientDocument", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="+")
    requested_at = models.DateTimeField(auto_now_add=True)
    reported_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Pedido de examen"
        verbose_name_plural = "Pedidos de exámenes"
        ordering = ["-requested_at"]


class ConsentTemplate(TenantAwareModel):
    """
    Plantilla reutilizable de consentimiento, clasificada por procedimiento
    (Sprint 37). El profesional selecciona una, la edita y guarda el
    consentimiento; puede crear, modificar y eliminar plantillas propias.
    """

    class Procedure(models.TextChoices):
        EXTRACCION = "extraccion", "Extracción dental"
        ENDODONCIA = "endodoncia", "Endodoncia"
        RESTAURACION = "restauracion", "Restauración"
        PROFILAXIS = "profilaxis", "Profilaxis"
        CIRUGIA = "cirugia", "Cirugía oral"
        IMPLANTE = "implante", "Implante"
        PROTESIS = "protesis", "Prótesis"
        ORTODONCIA = "ortodoncia", "Ortodoncia"
        OTRO = "otro", "Otro"

    procedure = models.CharField(max_length=20, choices=Procedure.choices)
    title = models.CharField(max_length=200)
    procedure_text = models.TextField(blank=True, help_text="Descripción del procedimiento.")
    benefits = models.TextField(blank=True)
    risks = models.TextField(blank=True)
    alternatives = models.TextField(blank=True)
    body_text = models.TextField(blank=True, help_text="Declaración de aceptación / cuerpo.")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="+")

    class Meta:
        verbose_name = "Plantilla de consentimiento"
        verbose_name_plural = "Plantillas de consentimiento"
        ordering = ["procedure", "title"]

    def __str__(self):
        return f"{self.get_procedure_display()} · {self.title}"


class ConsentAuditLog(TenantAwareModel):
    """Historial de auditoría de un consentimiento (Sprint 37)."""

    consent = models.ForeignKey(
        "InformedConsent", on_delete=models.CASCADE, related_name="audit_logs"
    )
    action = models.CharField(max_length=40)
    detail = models.CharField(max_length=255, blank=True)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="+")
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at"]

    def __str__(self):
        return f"{self.action} · {self.at:%Y-%m-%d %H:%M}"


class PeriodontalExam(TenantAwareModel):
    """
    Sesión de exploración periodontal (Sprint 52).

    Capa de datos NUEVA: el odontograma registra estados por superficie
    (caries, corona, implante…) y esto registra MEDICIONES por sitio
    (profundidad de sondaje, margen gingival, placa, sangrado). Son dos
    instrumentos distintos y por eso viven en tablas separadas: mezclarlos
    obligaría a que un registro de caries tuviera columnas de sondaje.

    Un paciente puede tener varias exploraciones a lo largo del tiempo, lo
    que permite comparar evolución periodontal entre sesiones.
    """

    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.CASCADE, related_name="periodontal_exams"
    )
    date = models.DateField(help_text="Fecha de la exploración.")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Exploración periodontal"
        verbose_name_plural = "Exploraciones periodontales"
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"Periodontograma {self.patient} · {self.date}"


class PeriodontalTooth(TenantAwareModel):
    """
    Mediciones de una pieza dentro de una exploración (Sprint 52).

    Réplica de la estructura de `MouthItem` del proyecto de referencia:
    presencia, implante, movilidad, furcación y SEIS SITIOS por pieza.

    Orden de los sitios (índices 0 a 5), convención periodontal:
        0,1,2 → vestibular: mesial, central, distal
        3,4,5 → palatino/lingual: mesial, central, distal

    Las series de seis valores se guardan en JSON en vez de veinticuatro
    columnas sueltas: mantiene el modelo legible, Postgres las indexa como
    JSONB y el serializador valida longitud y rango. El nivel de inserción
    (CAL) no se almacena porque es derivado: profundidad + margen.
    """

    SITES = 6

    exam = models.ForeignKey(
        PeriodontalExam, on_delete=models.CASCADE, related_name="teeth"
    )
    tooth_code = models.CharField(max_length=2, help_text="Código FDI, p. ej. 16.")

    is_present = models.BooleanField(default=True, help_text="Pieza presente en boca.")
    has_implant = models.BooleanField(default=False)
    mobility = models.PositiveSmallIntegerField(default=0, help_text="Grado 0 a 3.")
    furcation_buccal = models.PositiveSmallIntegerField(default=0, help_text="Grado 0 a 3.")
    furcation_lingual = models.PositiveSmallIntegerField(default=0)
    gum_width = models.PositiveSmallIntegerField(default=0, help_text="Ancho de encía en mm.")

    probing_depth = models.JSONField(default=list, blank=True, help_text="6 enteros (mm).")
    gingival_margin = models.JSONField(default=list, blank=True, help_text="6 enteros (mm).")
    bleeding = models.JSONField(default=list, blank=True, help_text="6 booleanos.")
    plaque = models.JSONField(default=list, blank=True, help_text="6 booleanos.")

    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Pieza del periodontograma"
        verbose_name_plural = "Piezas del periodontograma"
        ordering = ["tooth_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["exam", "tooth_code"], name="unique_tooth_per_periodontal_exam"
            )
        ]

    def __str__(self):
        return f"{self.tooth_code} · {self.exam.date}"

    @property
    def attachment_level(self):
        """Nivel de inserción por sitio: derivado, nunca almacenado."""
        pd = self.probing_depth or []
        gm = self.gingival_margin or []
        return [
            (pd[i] if i < len(pd) else 0) + (gm[i] if i < len(gm) else 0)
            for i in range(self.SITES)
        ]
