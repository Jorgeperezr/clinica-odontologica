from django.utils.functional import SimpleLazyObject
from django.utils.deprecation import MiddlewareMixin


def _resolve_tenant(request):
    """
    Resuelve el tenant a partir del usuario autenticado. Es perezoso a
    propósito: con JWT/DRF la autenticación ocurre DENTRO de la vista
    (no en el middleware de Django), así que si resolviéramos el tenant
    de forma temprana en process_request siempre saldría None. Usando
    SimpleLazyObject, request.tenant se evalúa la primera vez que una
    vista lo lee, momento en el que request.user ya está autenticado.
    """
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return getattr(user, "tenant", None)
    return None


class TenantMiddleware(MiddlewareMixin):
    """
    Adjunta request.tenant (perezoso) a partir del tenant del usuario.
    En la Fase 1 (una sola sede) casi es una formalidad, pero deja el
    código preparado para multi-sede: el día que haya varios tenants,
    solo cambia _resolve_tenant (ej. resolver por subdominio), sin tocar
    ninguna vista.
    """

    def process_request(self, request):
        request.tenant = SimpleLazyObject(lambda: _resolve_tenant(request))
