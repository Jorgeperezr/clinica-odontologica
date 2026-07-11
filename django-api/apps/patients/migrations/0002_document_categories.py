from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("patients", "0001_initial")]
    operations = [
        migrations.AlterField(
            model_name="patientdocument", name="doc_type",
            field=models.CharField(choices=[
                ("identification", "Identificación"), ("medical_order", "Orden médica"),
                ("referral", "Referencia"), ("radiograph", "Radiografía"),
                ("photo", "Foto clínica"), ("exam", "Examen / laboratorio"),
                ("report", "Informe"), ("other", "Otro"),
            ], max_length=20),
        ),
    ]
