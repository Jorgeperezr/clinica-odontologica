from django.db import migrations


def set_signed(apps, schema_editor):
    Consent = apps.get_model("clinical", "InformedConsent")
    Consent.objects.filter(signed_at__isnull=False).update(status="signed")


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("clinical", "0010_informedconsent_alternatives_and_more")]
    operations = [migrations.RunPython(set_signed, noop)]
