"""
Modelos de configuración y registro para la integración con WhatsApp
(RF-WSP, RN-WSP-01/02 — ver 04-Modelo-de-Datos, sección 8).

Implementación completa programada para el Sprint 10 del Roadmap.
Se deja aquí el modelo de plantillas porque Configuración (RF-CFG-05)
y el cliente del gateway (gateway_client.py) ya lo referencian.
"""


from django.db import models

from apps.common.models import TenantAwareModel


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


class ConfiguracionWhatsApp(TenantAwareModel):
    """
    La cuenta de WhatsApp Business de UNA clínica.

    Hasta ahora el gateway tenía una sola cuenta de Meta para toda la
    plataforma: todos los recordatorios salían del mismo número. Eso no
    vale cuando el paciente tiene que reconocer a su clínica en el
    remitente, y tampoco cuando cada clínica responde de lo que envía.

    **El token se guarda cifrado y no vuelve nunca al panel.** Se puede
    escribir y se puede saber SI está puesto —y sus últimos cuatro
    caracteres, para reconocerlo—, pero no leerlo. Un token de Meta
    permite enviar mensajes en nombre de la clínica: devolverlo al
    navegador lo expone a cualquier extensión instalada y a cualquiera
    que mire la pestaña de red.
    """

    # Identificadores, no secretos: se guardan en claro a propósito,
    # porque el panel tiene que poder enseñarlos para comprobarlos.
    phone_number_id = models.CharField(
        max_length=60, blank=True,
        verbose_name="Identificador de número (Meta)",
    )
    numero_visible = models.CharField(
        max_length=30, blank=True,
        verbose_name="Número tal como lo ve el paciente",
        help_text="Con código de país, p. ej. +593999111222.",
    )
    access_token_cifrado = models.TextField(blank=True, default="")

    plantilla_recordatorio = models.CharField(
        max_length=80, blank=True, default="recordatorio_cita",
        help_text="Nombre de la plantilla aprobada en Meta.",
    )
    activo = models.BooleanField(
        default=False,
        help_text="Mientras esté apagado no sale ningún mensaje automático.",
    )
    comprobado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Configuración de WhatsApp"
        verbose_name_plural = "Configuraciones de WhatsApp"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant"], name="una_configuracion_whatsapp_por_clinica",
            ),
        ]

    def __str__(self):
        return f"WhatsApp de {self.tenant_id}"

    # ── El token, siempre por estos dos ──────────────────────────────

    @property
    def token(self):
        from apps.common.secretos import descifrar
        return descifrar(self.access_token_cifrado)

    @token.setter
    def token(self, valor):
        from apps.common.secretos import cifrar
        self.access_token_cifrado = cifrar(valor)

    @property
    def pista_del_token(self):
        from apps.common.secretos import pista
        return pista(self.token)

    @property
    def esta_configurada(self):
        """
        Con las tres cosas puestas. Se comprueba aquí y no en la vista
        para que el panel, el envío y las pruebas coincidan en qué
        significa «configurada».
        """
        return bool(self.phone_number_id and self.token and self.plantilla_recordatorio)

    @property
    def puede_enviar(self):
        return self.activo and self.esta_configurada
