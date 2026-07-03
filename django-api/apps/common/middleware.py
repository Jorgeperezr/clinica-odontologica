from django.utils.deprecation import MiddlewareMixin


class TenantMiddleware(MiddlewareMixin):
    """
    Adjunta request.tenant a partir del tenant del usuario autenticado.

    En la Fase 1 (una sola sede) esto es casi una formalidad, pero deja
    el código ya preparado para el día en que existan múltiples tenants:
    ningún view necesitará cambiar, solo la forma de resolver el tenant
    aquí (ej. por subdominio) el día que haya más de una sede activa.
    """

    def process_request(self, request):
        request.tenant = None
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            request.tenant = getattr(user, "tenant", None)
