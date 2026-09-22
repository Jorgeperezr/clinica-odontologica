"""Quién decide a quién se premia."""

from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class PuedeGestionarLogros(BasePermission):
    """
    El administrador de la clínica siempre. Un doctor o auxiliar, solo
    si se le concedió el permiso al crearlo.

    Es un permiso aparte del rol a propósito: en una clínica con varios
    doctores no todos deciden quién se lleva un descuento, y darle esa
    potestad a cualquiera con bata convierte el programa en un favor
    personal en vez de en una regla de la clínica.
    """

    message = "No tienes permiso para gestionar rachas y logros."

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        if u.role == User.Role.ADMIN or u.is_superuser:
            return True
        return bool(getattr(u, "puede_gestionar_logros", False))
