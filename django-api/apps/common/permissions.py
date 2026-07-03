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
