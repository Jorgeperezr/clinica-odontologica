from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("patients", "0002_document_categories")]
    operations = [
        migrations.AddField(
            model_name="patient", name="sex",
            field=models.CharField(blank=True, choices=[("H", "Hombre"), ("M", "Mujer")],
                                   help_text="Literal A del formulario MSP 033.", max_length=1),
        ),
    ]
