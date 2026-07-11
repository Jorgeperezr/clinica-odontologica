from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("agenda", "0003_doctor_license")]
    operations = [
        migrations.AddField(
            model_name="doctor", name="signature_image",
            field=models.TextField(blank=True,
                help_text="Firma manuscrita del doctor (imagen base64, dibujada en pantalla). Se estampa en las recetas."),
        ),
    ]
