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
