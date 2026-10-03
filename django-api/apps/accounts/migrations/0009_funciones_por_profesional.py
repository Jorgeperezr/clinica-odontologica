"""
Los dos permisos sueltos por persona (logros y WhatsApp) pasan a ser dos
funciones más del catálogo de `apps/accounts/funciones.py`.

El orden importa: se crea `funciones`, se trasladan los permisos que
estuvieran concedidos y solo entonces se borran las columnas antiguas.
A quien no tenía ninguno de los dos no se le guarda nada: sigue con el
acceso heredado de su rol, que es exactamente el que tenía.
"""

from django.db import migrations, models

# Copia congelada de HEREDADAS en el momento de esta migración: la de
# `funciones.py` puede cambiar después y una migración no debe depender
# de código que cambia.
HEREDADAS = {
    "reception": {"agenda", "cobros", "mensajes_app"},
    "doctor": {"mensajes_app"},
    "auxiliary": {"inventario"},
}
CLAVES = ["agenda", "cobros", "mensajes_app", "logros", "inventario", "reportes", "whatsapp"]


def trasladar(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    concedidos = User.objects.filter(
        models.Q(puede_gestionar_logros=True) | models.Q(puede_gestionar_whatsapp=True),
        role__in=list(HEREDADAS),
    )
    for u in concedidos:
        base = {c: c in HEREDADAS[u.role] for c in CLAVES}
        base["logros"] = bool(u.puede_gestionar_logros)
        base["whatsapp"] = bool(u.puede_gestionar_whatsapp)
        u.funciones = base
        u.save(update_fields=["funciones"])


def deshacer(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for u in User.objects.exclude(funciones={}):
        u.puede_gestionar_logros = bool(u.funciones.get("logros"))
        u.puede_gestionar_whatsapp = bool(u.funciones.get("whatsapp"))
        u.save(update_fields=["puede_gestionar_logros", "puede_gestionar_whatsapp"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0008_user_preferencias"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="funciones",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Módulos de gestión que puede usar (agenda, cobros, inventario…). Vacío = los que su rol tenía antes de existir las funciones. Ver apps/accounts/funciones.py.",
            ),
        ),
        migrations.RunPython(trasladar, deshacer),
        migrations.RemoveField(model_name="user", name="puede_gestionar_logros"),
        migrations.RemoveField(model_name="user", name="puede_gestionar_whatsapp"),
    ]
