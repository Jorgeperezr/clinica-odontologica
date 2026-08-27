import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from apps.accounts.managers import UserManager
from apps.common.models import Tenant


class User(AbstractBaseUser, PermissionsMixin):
    """
    Usuario unificado para los 5 roles del SRS (RF-USR-03). El staff
    (admin/reception/doctor/auxiliary) usa email+password; el paciente
    usa únicamente teléfono+OTP (password inutilizable).
    """

    class Role(models.TextChoices):
        SUPERADMIN = "superadmin", "Super Administrador"
        ADMIN = "admin", "Administrador"
        RECEPTION = "reception", "Recepción"
        DOCTOR = "doctor", "Doctor"
        AUXILIARY = "auxiliary", "Auxiliar"
        PATIENT = "patient", "Paciente"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.PROTECT, related_name="users",
        null=True, blank=True,
        help_text="Nulo SOLO para el Super Administrador (opera sobre la plataforma, no dentro de una clínica).",
    )

    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
    full_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices)

    is_active = models.BooleanField(default=True)  # baja lógica — RF-USR-06
    is_staff = models.BooleanField(default=False)  # acceso al admin de Django

    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self):
        return self.email or self.phone or str(self.id)

    @property
    def is_patient(self):
        return self.role == self.Role.PATIENT


class DeviceToken(models.Model):
    """
    Token FCM para notificaciones push de la app móvil (RF-APP-05).
    Añadido en la Fase 5 (adenda al Modelo de datos, aprobada).
    """

    class Platform(models.TextChoices):
        IOS = "ios", "iOS"
        ANDROID = "android", "Android"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="device_tokens")
    fcm_token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(max_length=10, choices=Platform.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Token de dispositivo (push)"
        verbose_name_plural = "Tokens de dispositivo (push)"


class OTPCode(models.Model):
    """RF-USR-02, RF-USR-04: OTP por WhatsApp para login/recuperación de pacientes."""

    class Purpose(models.TextChoices):
        LOGIN = "login", "Inicio de sesión"
        RECOVERY = "recovery", "Recuperación de acceso"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="otp_codes")
    code_hash = models.CharField(max_length=128)  # nunca se guarda el código en texto plano
    purpose = models.CharField(max_length=10, choices=Purpose.choices)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Código OTP"
        verbose_name_plural = "Códigos OTP"
        indexes = [models.Index(fields=["user", "purpose", "expires_at"])]

    @property
    def is_valid(self):
        from django.utils import timezone

        return self.used_at is None and self.expires_at > timezone.now()


class AuditLog(models.Model):
    """
    RF-USR-05: registro de auditoría de todo acceso/modificación a datos
    clínicos o financieros, exigido también por la LOPDP (Ecuador).
    Se llena automáticamente vía apps.accounts.middleware.AuditLogMiddleware
    y/o de forma explícita desde las vistas que lo requieran.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="+", null=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="audit_logs")
    action = models.CharField(max_length=50)  # create, update, delete, view_clinical_record...
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=64, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro de auditoría"
        verbose_name_plural = "Registros de auditoría"
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["entity_type", "entity_id"]),
        ]

    def __str__(self):
        return f"{self.action} {self.entity_type}#{self.entity_id} por {self.user}"


class PasswordResetToken(models.Model):
    """
    RF-USR-04: token de recuperación de acceso para staff (enviado por
    correo). Los pacientes recuperan acceso reenviando un OTP, así que
    este modelo solo aplica a usuarios con contraseña.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reset_tokens")
    token_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Token de recuperación"
        verbose_name_plural = "Tokens de recuperación"

    @property
    def is_valid(self):
        from django.utils import timezone

        return self.used_at is None and self.expires_at > timezone.now()
