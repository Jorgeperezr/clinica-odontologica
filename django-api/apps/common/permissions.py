from rest_framework.permissions import BasePermission


class HasRole(BasePermission):
    """
    Permiso genérico basado en el rol del usuario (accounts.User.role),
    según la matriz de permisos definida en el SRS, sección 4.

    Uso en una vista:
        permission_classes = [HasRole.for_roles("admin", "reception")]
    """

    allowed_roles: tuple[str, ...] = ()

    @classmethod
    def for_roles(cls, *roles):
        return type("HasRoleDynamic", (cls,), {"allowed_roles": roles})

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.role in self.allowed_roles or user.is_superuser)
        )


class IsClinicAdmin(BasePermission):
    """
    Administrador DE UNA CLÍNICA: rol `admin` y con clínica asignada.

    A diferencia de `HasRole`, aquí no vale ser superusuario. El Super
    Administrador gestiona la plataforma y no tiene tenant, así que no es
    titular de los datos de ninguna clínica; dejarle pasar convertiría
    cualquier vista protegida con esto en una vía para operar sobre datos
    ajenos. Se usa en las acciones que solo tienen sentido como dueño de
    la clínica, como emitir o descifrar su copia de seguridad.
    """

    message = (
        "Solo la administradora o el administrador de la clínica puede realizar "
        "esta acción."
    )

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.role == "admin"
            and getattr(user, "tenant_id", None)
            and getattr(request, "tenant", None)
        )
