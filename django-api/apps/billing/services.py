"""
Lógica de negocio de facturación reutilizable (morosidad).
Centralizada aquí para que agenda, reportes y tareas Celery usen la
misma definición de "paciente moroso", sin duplicar reglas.
"""

from datetime import timedelta

from django.utils import timezone


def get_delinquency_days(tenant):
    """Lee el parámetro configurable 'dias_morosidad' (RF-CFG-05)."""
    from apps.configuration.models import SystemParameter

    param = SystemParameter.objects.filter(tenant=tenant, key="dias_morosidad").first()
    try:
        return int(param.value) if param else 30
    except (ValueError, TypeError):
        return 30


def is_patient_delinquent(patient, tenant):
    """
    Un paciente está moroso si tiene al menos una cuota no pagada cuya
    fecha de vencimiento superó el umbral de días configurado.
    Esta es la única definición de morosidad en el sistema (RN-AGN-01).
    """
    from apps.billing.models import Installment

    threshold_date = timezone.now().date() - timedelta(days=get_delinquency_days(tenant))
    return Installment.objects.filter(
        patient=patient,
        tenant=tenant,
        due_date__lt=threshold_date,
    ).exclude(status=Installment.Status.PAID).exists()


def get_overdue_installments(patient, tenant):
    """Devuelve las cuotas vencidas (no pagadas y ya pasada la fecha)."""
    from apps.billing.models import Installment

    today = timezone.now().date()
    return Installment.objects.filter(
        patient=patient, tenant=tenant, due_date__lt=today,
    ).exclude(status=Installment.Status.PAID)
