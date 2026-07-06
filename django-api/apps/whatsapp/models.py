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
