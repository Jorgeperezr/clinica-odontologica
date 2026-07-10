"""
Sprint 20: flujo de atención (inicio), control de recordatorios y token
de calendario por doctor.

calendar_token se añade en 3 pasos (nullable → poblar con UUID único por
fila → unique) porque añadir directamente un campo unique con default a
una tabla con filas existentes generaría el mismo valor para todas.
"""

import uuid

from django.db import migrations, models


def populate_calendar_tokens(apps, schema_editor):
    Doctor = apps.get_model("agenda", "Doctor")
    for doctor in Doctor.objects.all():
        doctor.calendar_token = uuid.uuid4()
        doctor.save(update_fields=["calendar_token"])


class Migration(migrations.Migration):
    dependencies = [
        ("agenda", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="appointment",
            name="attention_started_at",
            field=models.DateTimeField(
                blank=True, null=True,
                help_text="Cuándo el doctor inició la atención (flujo: llegó → en atención → finalizada).",
            ),
        ),
        migrations.AddField(
            model_name="appointment",
            name="reminder_sent_at",
            field=models.DateTimeField(
                blank=True, null=True,
                help_text="Cuándo se envió el recordatorio WhatsApp (evita duplicados).",
            ),
        ),
        # calendar_token en 3 pasos
        migrations.AddField(
            model_name="doctor",
            name="calendar_token",
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.RunPython(populate_calendar_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="doctor",
            name="calendar_token",
            field=models.UUIDField(
                default=uuid.uuid4, unique=True, editable=False,
                help_text="Token secreto del feed iCalendar (suscripción desde Google Calendar).",
            ),
        ),
    ]
