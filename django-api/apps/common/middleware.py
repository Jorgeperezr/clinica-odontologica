import logging
import time

from django.utils.deprecation import MiddlewareMixin
from django.utils.functional import SimpleLazyObject

from apps.common.logging import set_request_id

logger = logging.getLogger("apps.request")


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


class RequestLogMiddleware(MiddlewareMixin):
    """
    Traza de cada petición, con identificador de correlación (Sprint 75).

    Sin esto, la única señal de que algo va mal en producción es que un
    usuario llame por teléfono. Con esto queda, por cada petición: qué se
    pidió, qué se respondió, cuánto tardó y —si reventó— la traza
    completa, todo cosido por un mismo `request_id`.

    Qué NO se registra: nada que identifique a un paciente. En particular
    los VALORES de la cadena de consulta, porque
    `/api/v1/patients/?search=Pérez` lleva un apellido dentro de la URL;
    se guardan los nombres de los parámetros y no su contenido. Ver la
    explicación completa en `apps/common/logging.py`.

    Los 5xx se registran en ERROR con la traza, y lo demás en INFO. Se
    excluyen las sondas de salud: un balanceador las pide cada diez
    segundos y ahogarían el registro con ruido, que es como se pierde una
    incidencia de verdad.
    """

    RUTAS_SILENCIOSAS = ("/api/v1/health/", "/api/v1/ready/")

    def process_request(self, request):
        # Se respeta el id que venga del proxy: así una petición se sigue
        # de punta a punta aunque pase por nginx y por el gateway.
        entrante = request.headers.get("X-Request-ID", "")
        request.request_id = set_request_id(entrante[:64] or None)
        request._empezada_en = time.monotonic()

    def process_exception(self, request, exception):
        """
        Excepción no controlada. Es EL registro que hoy no existe: con
        DEBUG=False la traza no llega ni a la salida estándar.
        """
        logger.exception(
            "Excepción no controlada",
            extra={
                "method": request.method,
                "path": request.path,
                "query_keys": sorted(request.GET.keys()),
                **_quien(request),
            },
        )
        return None  # que Django siga con su manejo normal del 500

    def process_response(self, request, response):
        response["X-Request-ID"] = getattr(request, "request_id", "") or ""

        if request.path in self.RUTAS_SILENCIOSAS:
            return response

        empezada = getattr(request, "_empezada_en", None)
        duracion_ms = round((time.monotonic() - empezada) * 1000, 1) if empezada else None

        datos = {
            "method": request.method,
            "path": request.path,
            # Solo los NOMBRES de los parámetros: los valores llevan
            # nombres de pacientes en las búsquedas.
            "query_keys": sorted(request.GET.keys()),
            "status": response.status_code,
            "duration_ms": duracion_ms,
            **_quien(request),
        }

        if response.status_code >= 500:
            # `process_exception` ya habrá dejado la traza si hubo
            # excepción; esto cubre los 500 devueltos sin excepción.
            logger.error("Respuesta de error del servidor", extra=datos)
        elif response.status_code >= 400:
            logger.warning("Petición rechazada", extra=datos)
        else:
            logger.info("Petición atendida", extra=datos)
        return response


def _quien(request):
    """
    Quién hacía la petición, en identificadores y nunca en nombres.

    El correo o el nombre del usuario identifican a una persona; su UUID
    permite investigar sin exponerla. El id de clínica hace falta para
    saber a quién afecta una incidencia cuando hay varias.
    """
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return {"user_id": None, "tenant_id": None}
    tenant_id = getattr(user, "tenant_id", None)
    return {
        "user_id": str(user.pk),
        "user_role": getattr(user, "role", None),
        "tenant_id": str(tenant_id) if tenant_id else None,
    }
