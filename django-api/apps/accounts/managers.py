from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    """
    Manager personalizado: el staff se identifica por email+password;
    los pacientes no tienen password (solo OTP), así que password
    es opcional a nivel de manager pero el modelo lo maneja como
    "unusable password" en ese caso (ver User.set_unusable_password).
    """

    use_in_migrations = True

    def _create_user(self, email=None, phone=None, password=None, **extra_fields):
        if not email and not phone:
            raise ValueError("Se requiere email o teléfono para crear un usuario.")
        email = self.normalize_email(email) if email else None
        user = self.model(email=email, phone=phone, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email=None, phone=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, phone, password, **extra_fields)

    def create_superuser(self, email=None, phone=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "admin")
        if not password:
            raise ValueError("El superusuario requiere contraseña.")
        return self._create_user(email, phone, password, **extra_fields)
