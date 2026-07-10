"""
Crea el Super Administrador de la plataforma (sin clínica).

Uso:
    python manage.py createsuperadmin --email sa@plataforma.ec --password "ClaveLarga123"
"""

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Crea el Super Administrador del SaaS (usuario de plataforma, sin tenant)."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument("--full-name", default="Super Administrador")

    def handle(self, *args, **options):
        if len(options["password"]) < 10:
            raise CommandError("La contraseña debe tener al menos 10 caracteres.")
        if User.objects.filter(email__iexact=options["email"]).exists():
            raise CommandError("Ya existe un usuario con ese correo.")
        user = User(
            email=options["email"],
            full_name=options["full_name"],
            role=User.Role.SUPERADMIN,
            tenant=None,
        )
        user.set_password(options["password"])
        user.save()
        self.stdout.write(self.style.SUCCESS(f"Super Administrador creado: {user.email}"))
