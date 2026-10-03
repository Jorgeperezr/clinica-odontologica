"""
Autenticación JWT consciente del tenant (capa SaaS).

Extiende la autenticación estándar con dos rechazos que no son del
protocolo sino del negocio, y que por eso viven aquí: este es el único
punto por el que pasa toda petición autenticada de la API, así que es el
único que hay que revisar para saber quién puede operar.

  1. **Clínica desactivada.** Sin esto, un usuario con un token vigente
     seguiría trabajando después de que su clínica fuera dada de baja.

  2. **Contraseña puesta por otra persona.** Cuando el Super
     Administrador da de alta una clínica, entrega una contraseña
     temporal. Mientras no se cambie, esa cuenta solo puede hacer una
     cosa: elegir la suya. Si no, la entrega de credenciales no es una
     entrega: el dueño de la plataforma conserva indefinidamente la llave
     de los datos clínicos de esa clínica, que es justo lo contrario de
     lo que significa entregar unas credenciales.
"""

from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication


class CambioDeContrasenaRequerido(exceptions.PermissionDenied):
    """
    403 con un código propio para que el panel sepa a dónde llevar al
    usuario, en vez de enseñarle un «no tienes permiso» que no explica
    nada. Mismo patrón que el 409 `patient_delinquent` de la agenda.
    """

    default_code = "password_change_required"
    default_detail = (
        "Debes elegir tu propia contraseña antes de usar el sistema."
    )


# Lo único que se puede hacer con una contraseña temporal. `me` entra
# porque el panel lo pide nada más iniciar sesión para saber quién es, y
# el refresco porque perder la sesión a mitad del cambio sería absurdo.
RUTAS_CON_CONTRASENA_TEMPORAL = (
    "/api/v1/auth/change-password/",
    "/api/v1/auth/me/",
    "/api/v1/auth/token/refresh/",
)


class TenantAwareJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if user.tenant_id is not None and not user.tenant.is_active:
            raise exceptions.AuthenticationFailed(
                "La clínica de este usuario está desactivada.",
                code="tenant_inactive",
            )
        return user

    def authenticate(self, request):
        resultado = super().authenticate(request)
        if resultado is None:
            return None
        user, _ = resultado
        if getattr(user, "must_change_password", False):
            ruta = request.path
            if not any(ruta.startswith(p) for p in RUTAS_CON_CONTRASENA_TEMPORAL):
                raise CambioDeContrasenaRequerido()
        return resultado
