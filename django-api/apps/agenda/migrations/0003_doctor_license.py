from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("agenda", "0002_attention_flow_and_calendar")]
    operations = [
        migrations.AddField(
            model_name="doctor", name="license_number",
            field=models.CharField(blank=True, max_length=50,
                help_text="Nº de registro profesional (aparece en las recetas)."),
        ),
    ]
