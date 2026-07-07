import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("clinica_odontologica")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


# Tareas programadas (Celery Beat)
from celery.schedules import crontab  # noqa: E402

app.conf.beat_schedule = {
    "marcar-cuotas-vencidas-diario": {
        "task": "apps.billing.tasks.mark_overdue_installments",
        # Todos los días a las 00:30 (hora del servidor)
        "schedule": crontab(hour=0, minute=30),
    },
    "recordatorios-cita": {
        "task": "apps.whatsapp.tasks.send_appointment_reminders",
        # Cada hora, revisa citas dentro de la ventana de recordatorio
        "schedule": crontab(minute=0),
    },
    "recordatorios-pago": {
        "task": "apps.whatsapp.tasks.send_payment_reminders",
        # Una vez al día a las 09:00
        "schedule": crontab(hour=9, minute=0),
    },
}
