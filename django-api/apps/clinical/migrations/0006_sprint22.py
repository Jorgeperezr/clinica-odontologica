import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("clinical", "0005_evolution_created_by"),
        ("configuration", "0001_initial"),
        ("common", "0002_platform_v2"),
    ]

    operations = [
        migrations.AddField(
            model_name="evolution",
            name="follow_up_date",
            field=models.DateField(
                blank=True, null=True,
                help_text="Fecha de seguimiento: genera una alerta cuando llega (Sprint 22).",
            ),
        ),
        migrations.CreateModel(
            name="TreatmentPlanTemplate",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=150)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                             related_name="+", to="common.tenant")),
            ],
            options={
                "verbose_name": "Plantilla de plan de tratamiento",
                "verbose_name_plural": "Plantillas de planes de tratamiento",
                "unique_together": {("tenant", "name")},
            },
        ),
        migrations.CreateModel(
            name="TreatmentPlanTemplateItem",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("order", models.PositiveIntegerField(default=1)),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("template", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                               related_name="items", to="clinical.treatmentplantemplate")),
                ("treatment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                                related_name="+", to="configuration.treatment")),
            ],
            options={"ordering": ["order"]},
        ),
    ]
