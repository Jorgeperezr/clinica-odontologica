from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """
    Uniforma el formato de error de toda la API según lo definido en
    05-APIs-Clinica-Odontologica.md, sección 1 (Convenciones generales):

        { "error": { "code": "...", "message": "...", "details": {...} } }
    """
    response = exception_handler(exc, context)

    if response is None:
        return None

    error_code = getattr(exc, "default_code", exc.__class__.__name__.lower())
    detail = response.data

    if isinstance(detail, dict):
        message = detail.get("detail", "Ocurrió un error al procesar la solicitud.")
        details = {k: v for k, v in detail.items() if k != "detail"}
    else:
        message = str(detail)
        details = {}

    response.data = {
        "error": {
            "code": error_code,
            "message": message,
            "details": details,
        }
    }
    return response
