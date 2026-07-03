from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.common.models import Tenant


class Command(BaseCommand):
    help = "Crea un tenant por defecto (y opcionalmente un superusuario)."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-name", default="Clínica Principal")
        parser.add_argument("--tenant-ruc", default="")
        parser.add_argument("--superuser-email", default=None)
        parser.add_argument("--superuser-password", default=None)

    @transaction.atomic
    def handle(self, *args, **options):
        tenant, created = Tenant.objects.get_or_create(
            name=options["tenant_name"],
            defaults={"ruc": options["tenant_ruc"]},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Tenant creado: {tenant.name}"))
        else:
            self.stdout.write(f"Tenant ya existia: {tenant.name}")

        email = options["superuser_email"]
        password = options["superuser_password"]
        if email and password:
            if User.objects.filter(email=email).exists():
                self.stdout.write(f"El usuario {email} ya existe.")
            else:
                User.objects.create_superuser(
                    email=email, password=password, role="admin", tenant=tenant
                )
                self.stdout.write(self.style.SUCCESS(f"Superusuario creado: {email}"))
        else:
            self.stdout.write("Tenant listo. Cree el superusuario con: python manage.py createsuperuser")