"""
Rachas y logros del paciente.

La idea es de la clínica: premiar a quien acude a sus controles y sigue
las indicaciones. Tres decisiones que conviene entender antes de tocar
nada aquí.

**El beneficio es informativo, no toca el dinero.** Un logro DECLARA un
beneficio —«10% en tu próxima profilaxis»— y la app se lo enseña al
paciente, pero `pricing.py` no lo lee. El descuento lo aplica una
persona al presupuestar, viendo el aviso. Se hizo así a propósito: el
camino del dinero de esta aplicación ya tiene una precedencia delicada
(tarifario pactado → descuento del convenio → tarifario general →
catálogo), y meter ahí una regla automática que nadie ha visto funcionar
es la forma de acabar con facturas que no cuadran. Cuando las reglas
estén rodadas, conectarlo es un cambio pequeño y localizado.

**Se gana de dos maneras.** Hay reglas que el sistema evalúa solo
—asistir a las citas del mes, estar al día de pagos— y además admin o
doctor puede otorgar uno a mano. Las dos hacen falta: las reglas no ven
que alguien trajo a su hijo por primera vez sin que le insistieran.

**Lo otorgado no se recalcula.** Un logro concedido queda como un hecho
con su fecha, no como algo que se deduce cada vez que se mira. Si
mañana cambia la regla, lo que ya se premió sigue premiado; nadie pierde
un logro porque la clínica endureciera el criterio.
"""

from django.db import models

from apps.common.models import TenantAwareModel


class Logro(TenantAwareModel):
    """Lo que la clínica puede premiar. Cada clínica define los suyos."""

    class Regla(models.TextChoices):
        MANUAL = "manual", "Lo otorga una persona"
        ASISTENCIA_MENSUAL = "asistencia_mensual", "Asistió a sus citas del mes"
        AL_DIA_PAGOS = "al_dia_pagos", "Sin cuotas vencidas"

    nombre = models.CharField(max_length=80)
    descripcion = models.CharField(
        max_length=200, blank=True,
        help_text="Lo que el paciente lee en la app.",
    )
    # Una clave corta, no un archivo: la app decide con qué icono
    # pintarlo. Así cambiar el aspecto no obliga a resubir nada.
    icono = models.CharField(
        max_length=30, default="estrella",
        help_text="estrella · diente · racha · corazon · escudo · regalo",
    )
    beneficio = models.CharField(
        max_length=200, blank=True,
        help_text="Lo que gana. Informativo: no se aplica solo al presupuesto.",
    )
    regla = models.CharField(
        max_length=25, choices=Regla.choices, default=Regla.MANUAL,
    )
    # Solo para las reglas automáticas: cuántos meses seguidos cumpliendo
    # hacen falta. Con 1 se premia el primer mes; con 3, una racha.
    meses_requeridos = models.PositiveSmallIntegerField(default=1)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Logro"
        verbose_name_plural = "Logros"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "nombre"], name="logro_unico_por_clinica",
            ),
        ]

    def __str__(self):
        return self.nombre

    @property
    def es_automatico(self):
        return self.regla != self.Regla.MANUAL


class LogroDePaciente(TenantAwareModel):
    """
    Un logro concedido a un paciente, con su fecha.

    Se guarda el PERIODO al que corresponde (el primer día del mes) para
    las automáticas. Sin eso, evaluar dos veces el mismo mes concedería
    el logro dos veces, y la racha contaría el doble.
    """

    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.CASCADE, related_name="logros",
    )
    logro = models.ForeignKey(Logro, on_delete=models.PROTECT, related_name="concesiones")
    otorgado_en = models.DateTimeField(auto_now_add=True)
    # Nulo cuando lo concedió una regla: no hay persona detrás y fingir
    # que la hay confundiría a quien revise por qué se premió.
    otorgado_por = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="logros_otorgados",
    )
    periodo = models.DateField(
        null=True, blank=True,
        help_text="Primer día del mes que se premia. Nulo si es manual.",
    )
    nota = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "Logro de paciente"
        verbose_name_plural = "Logros de pacientes"
        ordering = ["-otorgado_en"]
        constraints = [
            # Solo para las automáticas, que llevan periodo. Las manuales
            # se pueden repetir: la clínica sabrá por qué premia dos veces.
            models.UniqueConstraint(
                fields=["patient", "logro", "periodo"],
                condition=models.Q(periodo__isnull=False),
                name="un_logro_por_paciente_y_periodo",
            ),
        ]

    def __str__(self):
        return f"{self.logro.nombre} → {self.patient}"
