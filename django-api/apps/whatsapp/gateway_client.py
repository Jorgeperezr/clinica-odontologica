"""
Cliente interno Django -> FastAPI (Arquitectura v1.2, sección 2 y
05-APIs-Clinica-Odontologica.md, sección 13.1).

Django/Celery decide CUÁNDO enviar un mensaje; este cliente solo
empaqueta la solicitud HTTP interna hacia el gateway de WhatsApp.
No conoce nada de la API de Meta — esa responsabilidad es 100% de
whatsapp-gateway/ (FastAPI).

**Cada clínica envía desde SU cuenta.** Si se pasa un `tenant`, sus
credenciales viajan en la petición y el gateway las usa en vez de las
suyas. Sin `tenant` —el código del OTP, que llega antes de saber de qué
clínica es nadie— se usan las de la plataforma, que es lo que había.

La decisión que conviene entender: **si la clínica tiene WhatsApp pero
sin configurar, NO se envía**. Caer a la cuenta de la plataforma haría
salir el mensaje desde un número que el paciente no reconoce, firmado
como si fuera su clínica. Es mejor no mandar nada y que se note.
"""

import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


def configuracion_lista(tenant):
    """
    La configuración de WhatsApp de la clínica si puede enviar, o None.

    Hacen falta DOS permisos distintos y se comprueban los dos: que el
    dueño de la plataforma le haya contratado la funcionalidad y que la
    clínica haya conectado y activado su cuenta. Quitar la funcionalidad
    tiene que parar los envíos aunque la cuenta siga conectada.
    """
    if tenant is None:
        return None
    from apps.common.funcionalidades import activa
    from apps.whatsapp.models import ConfiguracionWhatsApp

    if not activa(tenant, "whatsapp"):
        return None
    config = ConfiguracionWhatsApp.objects.filter(tenant=tenant).first()
    if config is None or not config.puede_enviar:
        return None
    return config


def credenciales_de(tenant):
    """
    Las de la clínica, o None si no las tiene listas.

    None significa «no envíes», no «usa las de la plataforma»: quien
    llama tiene que decidir a la vista de eso.
    """
    config = configuracion_lista(tenant)
    if config is None:
        return None
    return {
        "phone_number_id": config.phone_number_id,
        "access_token": config.token,
    }


def send_whatsapp_template(
    to_phone: str,
    template_name: str,
    language: str,
    variables: dict,
    patient_id: str,
    context: dict | None = None,
    tenant=None,
) -> dict:
    credenciales = None
    if tenant is not None:
        credenciales = credenciales_de(tenant)
        if credenciales is None:
            # Se registra en INFO y no en ERROR: que una clínica no haya
            # conectado WhatsApp es una decisión suya, no una avería.
            logger.info(
                "Sin envío de WhatsApp: la clínica no tiene su cuenta lista",
                extra={"tenant_id": str(getattr(tenant, "id", "")),
                       "template": template_name},
            )
            return {"status": "skipped", "detail": "La clínica no tiene WhatsApp configurado."}

    payload = {
        "to_phone": to_phone,
        "template_name": template_name,
        "language": language,
        "variables": variables,
        "patient_id": patient_id,
        "context": context or {},
    }
    if credenciales:
        # Viajan por la red interna, con el token de servicio de siempre.
        # La alternativa —que el gateway leyera la base de Django— sería
        # un acoplamiento mucho peor.
        payload["credenciales"] = credenciales
    headers = {"X-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

    try:
        response = httpx.post(
            f"{settings.WHATSAPP_GATEWAY_URL}/internal/send-template",
            json=payload,
            headers=headers,
            timeout=5.0,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        # No debe tumbar el flujo principal (ej. login por OTP) si el
        # gateway está caído; se registra para reintento/alerta.
        logger.error("Fallo al solicitar envío de WhatsApp: %s", exc)
        return {"status": "error", "detail": str(exc)}
