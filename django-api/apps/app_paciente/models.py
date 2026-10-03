"""
Lo que el paciente le pide a su clínica desde la app.

Dos cosas, y las dos con el mismo recorrido: el paciente escribe, la
recepción lo ve en la bandeja del panel y contesta, y el paciente ve la
respuesta en la app.

  · SolicitudCita: «quiero una cita tal día, por la mañana». No es una
    cita: la cita la crea la recepción, que es quien conoce la agenda
    de los doctores. Si el paciente pudiera reservar directamente, cada
    hueco libre en pantalla sería una promesa que la clínica no ha
    hecho.
  · MensajeConsultorio: una pregunta para el personal, con su respuesta.

Ninguno lleva el identificador del paciente en la petición: sale siempre
del token (ver `permissions.ficha_del_paciente`).
"""

from django.conf import settings
from django.db import models

from apps.common.models import TenantAwareModel


class SolicitudCita(TenantAwareModel):
    class Franja(models.TextChoices):
        MANANA = "manana", "Mañana"
        TARDE = "tarde", "Tarde"
        CUALQUIERA = "cualquiera", "Cualquier hora"

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        AGENDADA = "agendada", "Agendada"
        RECHAZADA = "rechazada", "No se pudo agendar"

    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.CASCADE, related_name="solicitudes_cita",
    )
    fecha_preferida = models.DateField()
    franja = models.CharField(max_length=12, choices=Franja.choices, default=Franja.CUALQUIERA)
    motivo = models.CharField(max_length=300, blank=True)
    estado = models.CharField(
        max_length=12, choices=Estado.choices, default=Estado.PENDIENTE, db_index=True,
    )
    cita = models.ForeignKey(
        "agenda.Appointment", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    respuesta = models.CharField(max_length=300, blank=True)
    atendida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    atendida_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Solicitud de cita desde la app"
        verbose_name_plural = "Solicitudes de cita desde la app"


class MensajeConsultorio(TenantAwareModel):
    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.CASCADE, related_name="mensajes_consultorio",
    )
    texto = models.TextField()
    respuesta = models.TextField(blank=True)
    respondido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    respondido_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Mensaje al consultorio"
        verbose_name_plural = "Mensajes al consultorio"
