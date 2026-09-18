from django.db import migrations, models
from django.db.models import F


def marcar_los_que_ya_estaban(apps, schema_editor):
    """
    Traduce a un campo lo que antes se adivinaba.

    Hasta ahora, «este precio lo puso una persona» se deducía comparando
    `estimated_price` con el precio de catálogo del tratamiento. Las filas
    que ya existen se crearon bajo esa regla, así que se les aplica la
    misma para no cambiarle el importe a ningún presupuesto en marcha:
    distinto del catálogo = lo escribió alguien.

    A partir de aquí la regla deja de existir y manda el campo.
    """
    Item = apps.get_model("clinical", "TreatmentPlanItem")
    Item.objects.exclude(estimated_price=F("treatment__base_price")).update(
        price_is_manual=True
    )


def volver_atras(apps, schema_editor):
    """Sin vuelta atrás que hacer: al quitar el campo se pierde y basta."""


class Migration(migrations.Migration):

    dependencies = [
        ("clinical", "0012_periodontalexam_periodontaltooth_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="treatmentplanitem",
            name="price_is_manual",
            field=models.BooleanField(
                default=False, verbose_name="Precio fijado a mano"
            ),
        ),
        migrations.RunPython(marcar_los_que_ya_estaban, volver_atras),
    ]
