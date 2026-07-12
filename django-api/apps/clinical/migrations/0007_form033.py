import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("clinical", "0006_sprint22"),
        ("patients", "0002_document_categories"),
        ("agenda", "0004_doctor_signature"),
        ("common", "0002_platform_v2"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="diagnosis", name="code",
            field=models.CharField(blank=True, help_text="Código CIE-10.", max_length=20),
        ),
        migrations.AddField(
            model_name="diagnosis", name="diagnosis_kind",
            field=models.CharField(choices=[("pre", "Presuntivo"), ("def", "Definitivo")],
                                   default="pre", max_length=3,
                                   help_text="PRE/DEF según formulario MSP 033."),
        ),
        migrations.AddField(
            model_name="toothrecord", name="mobility",
            field=models.PositiveSmallIntegerField(blank=True, null=True,
                                                   help_text="Movilidad 1-4 (formulario MSP 033)."),
        ),
        migrations.AddField(
            model_name="toothrecord", name="recession",
            field=models.PositiveSmallIntegerField(blank=True, null=True,
                                                   help_text="Recesión 1-4 (formulario MSP 033)."),
        ),
        migrations.CreateModel(
            name="Cie10",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=10, unique=True)),
                ("description", models.CharField(max_length=255)),
            ],
            options={"verbose_name": "Código CIE-10", "verbose_name_plural": "Códigos CIE-10",
                     "ordering": ["code"]},
        ),
        migrations.CreateModel(
            name="Form033Record",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("motivo_consulta", models.TextField(blank=True)),
                ("embarazada", models.BooleanField(blank=True, null=True)),
                ("enfermedad_actual", models.TextField(blank=True)),
                ("antecedentes_personales", models.JSONField(blank=True, default=dict)),
                ("antecedentes_familiares", models.JSONField(blank=True, default=dict)),
                ("temperatura", models.DecimalField(blank=True, decimal_places=1, max_digits=4, null=True)),
                ("pulso", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("frecuencia_respiratoria", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("presion_arterial", models.CharField(blank=True, max_length=15)),
                ("examen_estomatognatico", models.JSONField(blank=True, default=dict)),
                ("indicadores_salud_bucal", models.JSONField(blank=True, default=dict)),
                ("professional_snapshot", models.JSONField(blank=True, default=dict)),
                ("date", models.DateField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                 related_name="+", to=settings.AUTH_USER_MODEL)),
                ("doctor", models.ForeignKey(blank=True, null=True,
                                             on_delete=django.db.models.deletion.PROTECT,
                                             related_name="+", to="agenda.doctor")),
                ("patient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name="form033_records", to="patients.patient")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                             related_name="+", to="common.tenant")),
            ],
            options={"verbose_name": "Historia odontológica (Form 033)",
                     "verbose_name_plural": "Historias odontológicas (Form 033)",
                     "ordering": ["-date", "-created_at"]},
        ),
        migrations.CreateModel(
            name="ExamRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("category", models.CharField(choices=[("biometria", "Biometría"),
                                                       ("quimica_sanguinea", "Química sanguínea"),
                                                       ("rayos_x", "Rayos X"), ("otros", "Otros")],
                                              max_length=20)),
                ("detail", models.CharField(help_text="Examen solicitado.", max_length=255)),
                ("status", models.CharField(choices=[("pending", "Pedido"), ("reported", "Con informe")],
                                            default="pending", max_length=10)),
                ("report_notes", models.TextField(blank=True, help_text="M. Informe de exámenes.")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("reported_at", models.DateTimeField(blank=True, null=True)),
                ("patient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name="exam_requests", to="patients.patient")),
                ("report_document", models.ForeignKey(blank=True, null=True,
                                                      on_delete=django.db.models.deletion.SET_NULL,
                                                      related_name="+", to="patients.patientdocument")),
                ("requested_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                   related_name="+", to=settings.AUTH_USER_MODEL)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                             related_name="+", to="common.tenant")),
            ],
            options={"verbose_name": "Pedido de examen", "verbose_name_plural": "Pedidos de exámenes",
                     "ordering": ["-requested_at"]},
        ),
    ]
