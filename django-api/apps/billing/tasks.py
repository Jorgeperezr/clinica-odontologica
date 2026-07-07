"""
Tareas programadas de facturación (Celery Beat).
"""

from celery import shared_task


@shared_task
def mark_overdue_installments():
    """
    Marca como 'overdue' las cuotas pendientes cuya fecha de vencimiento
    ya pasó. Se programa diariamente vía Celery Beat. Mantiene el estado
    de las cuotas consistente para los reportes y el bloqueo por morosidad.
    """
    from django.utils import timezone

    from apps.billing.models import Installment

    today = timezone.now().date()
    updated = (
        Installment.objects.filter(
            due_date__lt=today, status=Installment.Status.PENDING
        )
        .update(status=Installment.Status.OVERDUE)
    )
    return {"marked_overdue": updated}
