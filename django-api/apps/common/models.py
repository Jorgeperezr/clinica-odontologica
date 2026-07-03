import uuid

from django.db import models


class Tenant(models.Model):
    """
    Representa una sede/clínica. En la Fase 1 solo existe un Tenant activo,
    pero el campo tenant_id ya se propaga a todas las tablas del dominio
    desde el día uno (Arquitectura v1.2, sección "Escalabilidad").
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    ruc = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tenant (clínica)"
        verbose_name_plural = "Tenants (clínicas)"

    def __str__(self):
        return self.name


class TenantAwareModel(models.Model):
    """
    Clase base abstracta para cualquier modelo del dominio que deba
    filtrarse por sede. Todas las apps de negocio (patients, agenda,
    clinical, billing, inventory, etc.) heredan de esta clase en vez
    de repetir el campo tenant_id manualmente.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    """
    Borrado lógico obligatorio para tablas clínicas y financieras
    (SRS, sección 0 "Convenciones generales" del Modelo de datos):
    nunca se hace DELETE físico sobre datos de salud o de pagos.
    """

    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def soft_delete(self):
        from django.utils import timezone

        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_active", "deleted_at"])
