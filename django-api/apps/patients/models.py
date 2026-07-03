"""
Gestión de pacientes (RF-PAC) — ver 04-Modelo-de-Datos, sección 2.
Implementado en el Sprint 1-2 del Roadmap.
"""

from django.db import models

from apps.accounts.models import User
from apps.common.models import SoftDeleteModel, TenantAwareModel


class Patient(TenantAwareModel, SoftDeleteModel):
    """RF-PAC-01. Borrado lógico: nunca se elimina físicamente un paciente."""

    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="patient_profile",
        help_text="Solo se llena si el paciente usa la app/portal.",
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    national_id = models.CharField(max_length=20, help_text="Cédula o pasaporte")
    birth_date = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    photo = models.ImageField(upload_to="patients/photos/", null=True, blank=True)

    class Meta:
        verbose_name = "Paciente"
        verbose_name_plural = "Pacientes"
        constraints = [
            # RN-PAC-01: unicidad de cédula por sede (no global, por si en
            # el futuro dos sedes atienden poblaciones distintas).
            models.UniqueConstraint(
                fields=["tenant", "national_id"],
                condition=models.Q(is_active=True),
                name="unique_national_id_per_tenant",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "national_id"]),
            models.Index(fields=["tenant", "last_name", "first_name"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.national_id})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class MedicalBackground(models.Model):
    """RF-PAC-03. Uno a uno con el paciente."""

    patient = models.OneToOneField(
        Patient, on_delete=models.CASCADE, related_name="medical_background"
    )
    allergies = models.TextField(blank=True)
    medications = models.TextField(blank=True)
    conditions = models.TextField(blank=True)
    is_pregnant = models.BooleanField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        verbose_name = "Antecedente médico"
        verbose_name_plural = "Antecedentes médicos"


class PatientDocument(models.Model):
    """RF-PAC-04. Documentos adjuntos al expediente."""

    class DocType(models.TextChoices):
        IDENTIFICATION = "identification", "Identificación"
        MEDICAL_ORDER = "medical_order", "Orden médica"
        REFERRAL = "referral", "Referencia"
        OTHER = "other", "Otro"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="documents")
    doc_type = models.CharField(max_length=20, choices=DocType.choices)
    file = models.FileField(upload_to="patients/documents/")
    description = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="+")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Documento de paciente"
        verbose_name_plural = "Documentos de paciente"
