"""
Comando de arranque en frío.

Resuelve el problema chicken-and-egg del primer despliegue: el modelo
User exige un tenant, pero para crear el primer usuario (superuser) aún
no existe ningún tenant. Este comando:
  1. Crea un tenant por defecto.
  2. Siembra las 5 especialidades base del SRS.
  3. Siembra los parámetros del sistema por defecto.
  4. Opcionalmente crea un superusuario.
Todo de forma idempotente (se puede correr varias veces sin duplicar).
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.common.models import Tenant


class Command(BaseCommand):
    help = "Prepara el primer arranque: tenant, especialidades, parámetros y (opcional) superusuario."

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

        self._seed_specialties(tenant)
        self._seed_parameters(tenant)
        self._seed_odontogram_states(tenant)

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

    def _seed_specialties(self, tenant):
        from apps.specialties.models import Specialty

        base = [
            "Clínica general",
            "Ortodoncia",
            "Endodoncia",
            "Periodoncia",
            "Odontopediatría",
        ]
        added = 0
        for name in base:
            _, was_created = Specialty.objects.get_or_create(tenant=tenant, name=name)
            added += int(was_created)
        if added:
            self.stdout.write(self.style.SUCCESS(f"Especialidades sembradas: {added} nuevas."))

    def _seed_parameters(self, tenant):
        from apps.configuration.models import SystemParameter

        added = 0
        for key, (value, description) in SystemParameter.DEFAULTS.items():
            _, was_created = SystemParameter.objects.get_or_create(
                tenant=tenant, key=key, defaults={"value": value, "description": description}
            )
            added += int(was_created)
        if added:
            self.stdout.write(self.style.SUCCESS(f"Parámetros del sistema sembrados: {added} nuevos."))

    def _seed_odontogram_states(self, tenant):
        from apps.clinical.models import OdontogramState

        added = 0
        for code, (label, color, order) in OdontogramState.DEFAULTS.items():
            _, was_created = OdontogramState.objects.get_or_create(
                tenant=tenant, code=code,
                defaults={"label": label, "color": color, "order": order},
            )
            added += int(was_created)
        if added:
            self.stdout.write(self.style.SUCCESS(f"Estados del odontograma sembrados: {added} nuevos."))
