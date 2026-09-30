"""
La plataforma pasa a llamarse Clinube.

Además del valor por omisión, se renombra la configuración que ya
existe, pero solo si seguía con el nombre de fábrica: si el Super
Administrador la había bautizado a mano, se respeta.
"""

from django.db import migrations, models

ANTERIOR = "Plataforma Odontológica"
NUEVO = "Clinube"


def renombrar(apps, schema_editor):
    Config = apps.get_model("common", "PlatformConfiguration")
    Config.objects.filter(platform_name=ANTERIOR).update(platform_name=NUEVO)


def deshacer(apps, schema_editor):
    Config = apps.get_model("common", "PlatformConfiguration")
    Config.objects.filter(platform_name=NUEVO).update(platform_name=ANTERIOR)


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0004_tenant_modulos_clinica"),
    ]

    operations = [
        migrations.AlterField(
            model_name="platformconfiguration",
            name="platform_name",
            field=models.CharField(default="Clinube", max_length=120),
        ),
        migrations.RunPython(renombrar, deshacer),
    ]
