"""
Quién es el paciente que pregunta (Sprint 89).

Toda esta superficie existe para la app móvil, y tiene una regla que no
admite excepciones: **el paciente nunca elige de quién son los datos**.
No hay un parámetro con el identificador del paciente en ninguna ruta ni
en ninguna consulta; el paciente sale siempre del token, y de ahí su
ficha. Un identificador en la petición sería una invitación a pedir la
historia clínica del vecino.

Por eso la resolución vive aquí y no repetida en cada vista: es el único
punto donde se decide de quién se está hablando, y por tanto el único
que hay que revisar cuando alguien pregunte si esto es seguro.
"""

from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import User


class EsPaciente(permissions.BasePermission):
    """Autenticado Y con rol de paciente. El personal usa el panel."""

    message = "Esta sección es de la aplicación del paciente."

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.role == User.Role.PATIENT)


def ficha_del_paciente(request):
    """
    La ficha clínica de quien pregunta.

    Un usuario con rol de paciente puede existir sin ficha —por ejemplo si
    se creó la cuenta antes que el registro clínico—. En ese caso NO se
    devuelve una lista vacía, que se leería como «no tienes citas»: se
    responde que la cuenta no está enlazada, que es lo que de verdad pasa
    y lo que el soporte de la clínica puede resolver.
    """
    from apps.patients.models import Patient

    ficha = Patient.objects.filter(
        user=request.user, tenant=request.tenant,
    ).select_related("agreement").first()
    if ficha is None:
        raise PermissionDenied(
            "Tu cuenta aún no está enlazada con tu ficha en la clínica. "
            "Comunícate con la recepción para activarla."
        )
    return ficha
