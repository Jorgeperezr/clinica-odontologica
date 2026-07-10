"""
Autenticación JWT consciente del tenant (capa SaaS).

Extiende la autenticación estándar para rechazar tokens de usuarios
cuya clínica fue desactivada por el Super Administrador. Sin esto,
un usuario con un token vigente podría seguir operando después de que
su clínica fuera dada de baja.
"""

from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication


class TenantAwareJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if user.tenant_id is not None and not user.tenant.is_active:
            raise exceptions.AuthenticationFailed(
                "La clínica de este usuario está desactivada.",
                code="tenant_inactive",
            )
        return user
