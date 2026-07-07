"""
Modelos de configuración y registro para la integración con WhatsApp
(RF-WSP, RN-WSP-01/02 — ver 04-Modelo-de-Datos, sección 8).

Implementación completa programada para el Sprint 10 del Roadmap.
Se deja aquí el modelo de plantillas porque Configuración (RF-CFG-05)
y el cliente del gateway (gateway_client.py) ya lo referencian.
"""


from apps.common.models import TenantAwareModel
from django.db import models


class WhatsAppTemplate(TenantAwareModel):
    class Category(models.TextChoices):
        AUTHENTICATION = "authentication", "Autenticación"
        UTILITY = "utility", "Utilidad"
        MARKETING = "marketing", "Marketing"

    name = models.CharField(max_length=100)
    meta_template_name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=Category.choices)
    language = models.CharField(max_length=10, default="es")
    variables = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Plantilla de WhatsApp"
        verbose_name_plural = "Plantillas de WhatsApp"

    def __str__(self):
        return self.name


class WhatsAppMessageLog(TenantAwareModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "En cola"
        SENT = "sent", "Enviado"
        DELIVERED = "delivered", "Entregado"
        READ = "read", "Leído"
        FAILED = "failed", "Fallido"

    patient_phone = models.CharField(max_length=20)
    template = models.ForeignKey(WhatsAppTemplate, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    provider_message_id = models.CharField(max_length=100, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Registro de mensaje WhatsApp"
        verbose_name_plural = "Registros de mensajes WhatsApp"


class WhatsAppOptIn(TenantAwareModel):
    """
    Registro de consentimiento del paciente para recibir mensajes por
    WhatsApp (RN-WSP-02). Exigencia de Meta y de la LOPDP: guardamos
    cuándo y por qué canal el paciente aceptó, y si revocó.
    """

    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.CASCADE, related_name="whatsapp_optins"
    )
    opted_in_at = models.DateTimeField(auto_now_add=True)
    channel = models.CharField(
        max_length=50, default="registro_recepcion",
        help_text="Canal por el que el paciente dio su consentimiento.",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Opt-in de WhatsApp"
        verbose_name_plural = "Opt-ins de WhatsApp"

    def __str__(self):
        estado = "revocado" if self.revoked_at else "activo"
        return f"Opt-in {self.patient} ({estado})"

    @property
    def is_active(self):
        return self.revoked_at is None
