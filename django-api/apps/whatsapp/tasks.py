"""
Tareas de automatización de WhatsApp (Celery).
Django decide CUÁNDO enviar cada mensaje; el microservicio FastAPI
decide CÓMO llega a Meta. Estas tareas solo preparan el contenido y
delegan el envío vía gateway_client.
"""

import logging
from datetime import timedelta

from celery import shared_task

logger = logging.getLogger(__name__)


def _has_active_optin(patient, tenant):
    """Solo se envía a pacientes con opt-in activo (RN-WSP-02)."""
    from apps.whatsapp.models import WhatsAppOptIn

    return WhatsAppOptIn.objects.filter(
        patient=patient, tenant=tenant, revoked_at__isnull=True
    ).exists()


@shared_task
def send_appointment_reminders():
    """
    Recordatorio de cita (RF-WSP-02). Se programa vía Celery Beat.
    Envía a las citas cuya hora de inicio cae dentro de la ventana
    configurable (ventana_recordatorio_horas) y que aún no fueron
    recordadas. Respeta el opt-in del paciente.
    """
    from django.utils import timezone

    from apps.agenda.models import Appointment
    from apps.configuration.models import SystemParameter
    from apps.whatsapp.gateway_client import send_whatsapp_template

    now = timezone.now()
    sent = 0

    # Agrupar por tenant para leer su ventana de recordatorio
    for param in SystemParameter.objects.filter(key="ventana_recordatorio_horas"):
        try:
            window_hours = int(param.value)
        except (ValueError, TypeError):
            window_hours = 24
        window_end = now + timedelta(hours=window_hours)

        appointments = Appointment.objects.filter(
            tenant=param.tenant,
            scheduled_start__gte=now,
            scheduled_start__lte=window_end,
            status__in=[Appointment.Status.PENDING, Appointment.Status.CONFIRMED],
        ).select_related("patient", "doctor")

        for appt in appointments:
            if not _has_active_optin(appt.patient, param.tenant):
                continue
            send_whatsapp_template(
                to_phone=appt.patient.phone,
                template_name="recordatorio_cita",
                language="es",
                variables={
                    "1": appt.patient.full_name,
                    "2": appt.scheduled_start.strftime("%d/%m/%Y %H:%M"),
                },
                patient_id=str(appt.patient.id),
                context={"appointment_id": str(appt.id)},
            )
            sent += 1

    return {"reminders_sent": sent}


@shared_task
def send_payment_reminders():
    """
    Recordatorio de pago (RF-WSP-06) para cuotas próximas a vencer o
    vencidas. Se programa vía Celery Beat.
    """
    from django.utils import timezone

    from apps.billing.models import Installment
    from apps.whatsapp.gateway_client import send_whatsapp_template

    today = timezone.now().date()
    soon = today + timedelta(days=3)
    sent = 0

    installments = Installment.objects.filter(
        due_date__lte=soon,
    ).exclude(status=Installment.Status.PAID).select_related("patient")

    for inst in installments:
        if not _has_active_optin(inst.patient, inst.tenant):
            continue
        send_whatsapp_template(
            to_phone=inst.patient.phone,
            template_name="recordatorio_pago",
            language="es",
            variables={
                "1": inst.patient.full_name,
                "2": str(inst.amount),
                "3": inst.due_date.strftime("%d/%m/%Y"),
            },
            patient_id=str(inst.patient.id),
            context={"installment_id": str(inst.id)},
        )
        sent += 1

    return {"payment_reminders_sent": sent}


@shared_task
def notify_doctor_patient_arrived(appointment_id):
    """
    Aviso al doctor de que su paciente llegó (RF-WSP-05). Se dispara
    desde el check-in de la agenda, no por Beat.
    """
    from apps.agenda.models import Appointment
    from apps.whatsapp.gateway_client import send_whatsapp_template

    try:
        appt = Appointment.objects.select_related("patient", "doctor", "doctor__user").get(
            id=appointment_id
        )
    except Appointment.DoesNotExist:
        logger.warning("Cita %s no encontrada para aviso de llegada.", appointment_id)
        return {"sent": False}

    doctor_phone = appt.doctor.user.phone
    if not doctor_phone:
        return {"sent": False, "reason": "doctor sin teléfono"}

    send_whatsapp_template(
        to_phone=doctor_phone,
        template_name="aviso_llegada",
        language="es",
        variables={"1": appt.patient.full_name},
        patient_id=str(appt.patient.id),
        context={"appointment_id": str(appt.id)},
    )
    return {"sent": True}
