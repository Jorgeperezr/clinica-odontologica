"""
Agenda (RF-AGN) — ver 04-Modelo-de-Datos, sección 3.
Sprint 3: Doctor (perfil extendido) y Appointment (citas) con estados,
check-in/out y validación de solapamiento. El bloqueo por morosidad
(RF-AGN-07) se activa en el Sprint 9, cuando exista billing.
La sincronización con Google Calendar (RF-AGN-06) se estructura aquí y
se completa con OAuth2 más adelante en este mismo sprint.
"""

import uuid

from django.db import models

from apps.accounts.models import User
from apps.common.models import TenantAwareModel
from apps.specialties.models import Specialty


class Doctor(TenantAwareModel):
    """
    Perfil extendido de un User con role=doctor. Se separa del User para
    guardar datos propios del doctor (color en agenda, token de Google
    Calendar) sin ensuciar el modelo de autenticación.
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="doctor_profile"
    )
    specialties = models.ManyToManyField(
        Specialty, related_name="doctors", blank=True
    )
    calendar_color = models.CharField(
        max_length=7, default="#3b82f6", help_text="Color hex para distinguirlo en la agenda."
    )
    google_calendar_token = models.JSONField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Doctor"
        verbose_name_plural = "Doctores"

    calendar_token = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False,
        help_text="Token secreto del feed iCalendar (suscripción desde Google Calendar).",
    )

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        # Usa el nombre del usuario (añadido en el Sprint 12); si el
        # usuario no tiene nombre cargado, cae al email como respaldo.
        return self.user.full_name or self.user.email or str(self.user_id)


class Appointment(TenantAwareModel):
    """Cita odontológica (RF-AGN-03, 04, 05)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        CONFIRMED = "confirmed", "Confirmada"
        CANCELLED = "cancelled", "Cancelada"
        RESCHEDULED = "rescheduled", "Reagendada"
        COMPLETED = "completed", "Completada"
        NO_SHOW = "no_show", "No asistió"

    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.PROTECT, related_name="appointments"
    )
    doctor = models.ForeignKey(
        Doctor, on_delete=models.PROTECT, related_name="appointments"
    )
    # Tratamiento estimado (opcional al agendar). FK textual para no crear
    # dependencia circular con configuration en tiempo de import.
    treatment = models.ForeignKey(
        "configuration.Treatment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
    )
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.PENDING
    )
    notes = models.TextField(blank=True)

    checkin_at = models.DateTimeField(null=True, blank=True)
    attention_started_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Cuándo el doctor inició la atención (flujo: llegó → en atención → finalizada).",
    )
    checkout_at = models.DateTimeField(null=True, blank=True)
    reminder_sent_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Cuándo se envió el recordatorio WhatsApp (evita duplicados).",
    )

    google_calendar_event_id = models.CharField(max_length=255, blank=True)

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        verbose_name = "Cita"
        verbose_name_plural = "Citas"
        indexes = [
            models.Index(fields=["tenant", "doctor", "scheduled_start"]),
            models.Index(fields=["tenant", "scheduled_start"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.patient} con {self.doctor} — {self.scheduled_start:%Y-%m-%d %H:%M}"

    def overlaps_with_existing(self):
        """
        Valida que la cita no se solape con otra del mismo doctor que no
        esté cancelada. Regla de negocio en el modelo, no en el cliente.
        """
        clash = Appointment.objects.filter(
            doctor=self.doctor,
            scheduled_start__lt=self.scheduled_end,
            scheduled_end__gt=self.scheduled_start,
        ).exclude(status=self.Status.CANCELLED)
        if self.pk:
            clash = clash.exclude(pk=self.pk)
        return clash.exists()
