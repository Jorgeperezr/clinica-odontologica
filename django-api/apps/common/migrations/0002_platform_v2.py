import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("common", "0001_initial")]

    operations = [
        migrations.AddField(model_name="tenant", name="address",
                            field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name="tenant", name="phone",
                            field=models.CharField(blank=True, max_length=30)),
        migrations.AddField(model_name="tenant", name="email",
                            field=models.EmailField(blank=True, max_length=254)),
        migrations.CreateModel(
            name="PlatformConfiguration",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("platform_name", models.CharField(default="Plataforma Odontológica", max_length=120)),
                ("logo_url", models.URLField(blank=True)),
                ("smtp_host", models.CharField(blank=True, max_length=255)),
                ("smtp_port", models.PositiveIntegerField(default=587)),
                ("smtp_user", models.CharField(blank=True, max_length=255)),
                ("smtp_password", models.CharField(blank=True, max_length=255)),
                ("timezone", models.CharField(default="America/Guayaquil", max_length=64)),
                ("currency", models.CharField(default="USD", max_length=8)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Configuración de plataforma",
                "verbose_name_plural": "Configuración de plataforma",
            },
        ),
    ]
