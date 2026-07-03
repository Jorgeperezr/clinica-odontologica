from django.utils.deprecation import MiddlewareMixin

from apps.accounts.models import AuditLog

# Solo se audita automáticamente lo que modifica estado; las lecturas
# (GET) se auditan de forma explícita únicamente donde el SRS lo exige
# (ej. ver historia clínica), para no inflar la tabla con cada GET.
AUDITED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class AuditLogMiddleware(MiddlewareMixin):
    """
    RF-USR-05: registra automáticamente toda escritura hecha por un
    usuario autenticado. No reemplaza el registro explícito y más rico
    en contexto que cada vista puede añadir (ver AuditLog.metadata).
    """

    def process_response(self, request, response):
        user = getattr(request, "user", None)
        if (
            request.method in AUDITED_METHODS
            and user is not None
            and getattr(user, "is_authenticated", False)
            and 200 <= response.status_code < 300
        ):
            AuditLog.objects.create(
                tenant=getattr(request, "tenant", None),
                user=user,
                action=request.method.lower(),
                entity_type=request.path,
                entity_id="",
                ip_address=self._get_client_ip(request),
                metadata={"status_code": response.status_code},
            )
        return response

    @staticmethod
    def _get_client_ip(request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
