"""
Las reglas que se evalúan solas.

Deliberadamente pocas y muy definidas. Una regla vaga —«es un buen
paciente»— no se puede comprobar, no se puede explicar a quien pregunte
por qué no le tocó, y acaba premiando ruido.

Cada regla responde a una pregunta cerrada sobre UN mes concreto, y
recibe el mes como argumento en vez de mirar «hoy». Así se puede
reevaluar el pasado, y las pruebas no dependen de la fecha en que se
ejecuten, que es de donde han salido varios fallos de este proyecto.
"""

from datetime import date

from django.db.models import Q


def _limites_del_mes(mes):
    """Del primer día de `mes` al primero del siguiente."""
    inicio = date(mes.year, mes.month, 1)
    fin = date(mes.year + 1, 1, 1) if mes.month == 12 else date(mes.year, mes.month + 1, 1)
    return inicio, fin


def asistio_a_sus_citas(paciente, mes):
    """
    Tuvo al menos una cita completada ese mes y ninguna falta.

    «Ninguna falta» incluye las canceladas por el paciente y los
    `no_show`. Si no tuvo ninguna cita, NO cuenta: no se premia no
    haber ido nunca, que sería premiar justo lo contrario.
    """
    from apps.agenda.models import Appointment

    inicio, fin = _limites_del_mes(mes)
    citas = Appointment.objects.filter(
        patient=paciente, tenant=paciente.tenant,
        scheduled_start__date__gte=inicio, scheduled_start__date__lt=fin,
    )
    completadas = citas.filter(status=Appointment.Status.COMPLETED).count()
    faltas = citas.filter(
        Q(status=Appointment.Status.NO_SHOW) | Q(status=Appointment.Status.CANCELLED)
    ).count()
    return completadas >= 1 and faltas == 0


def estuvo_al_dia(paciente, mes):
    """
    Cerró el mes sin ninguna cuota vencida.

    Se mira el estado al ÚLTIMO día del mes, no hoy: el logro de
    septiembre no puede depender de si hoy, en noviembre, debe algo.
    """
    from apps.billing.models import Installment

    _, fin = _limites_del_mes(mes)
    vencidas = Installment.objects.filter(
        patient=paciente, tenant=paciente.tenant, due_date__lt=fin,
    ).exclude(status=Installment.Status.PAID).count()
    return vencidas == 0


REGLAS = {
    "asistencia_mensual": asistio_a_sus_citas,
    "al_dia_pagos": estuvo_al_dia,
}


def cumple(logro, paciente, mes):
    """¿Este paciente cumple este logro en este mes?"""
    fn = REGLAS.get(logro.regla)
    return bool(fn and fn(paciente, mes))


def meses_hacia_atras(desde, cuantos):
    """`cuantos` primeros-de-mes, terminando en el de `desde`."""
    meses = []
    anio, mes = desde.year, desde.month
    for _ in range(cuantos):
        meses.append(date(anio, mes, 1))
        mes -= 1
        if mes == 0:
            anio, mes = anio - 1, 12
    return list(reversed(meses))


def racha_de(paciente, logro, hasta):
    """
    Cuántos meses seguidos lleva cumpliéndolo, contando hacia atrás.

    Es lo que convierte un logro suelto en una racha, y lo que la app
    enseña como «3 meses seguidos».
    """
    seguidos = 0
    anio, mes = hasta.year, hasta.month
    while True:
        if not cumple(logro, paciente, date(anio, mes, 1)):
            return seguidos
        seguidos += 1
        mes -= 1
        if mes == 0:
            anio, mes = anio - 1, 12
        # Tope de seguridad: sin esto, un logro que se cumple siempre
        # —«sin cuotas vencidas» en un paciente que nunca debió nada—
        # haría girar este bucle hasta el año 1.
        if seguidos >= 120:
            return seguidos
