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
}
