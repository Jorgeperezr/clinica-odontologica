"""
Cliente interno Django -> FastAPI (Arquitectura v1.2, sección 2 y
05-APIs-Clinica-Odontologica.md, sección 13.1).

Django/Celery decide CUÁNDO enviar un mensaje; este cliente solo
empaqueta la solicitud HTTP interna hacia el gateway de WhatsApp.
No conoce nada de la API de Meta — esa responsabilidad es 100% de
whatsapp-gateway/ (FastAPI).
"""

import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


def send_whatsapp_template(
    to_phone: str,
    template_name: str,
    language: str,
    variables: dict,
    patient_id: str,
    context: dict | None = None,
) -> dict:
    payload = {
        "to_phone": to_phone,
        "template_name": template_name,
        "language": language,
        "variables": variables,
        "patient_id": patient_id,
        "context": context or {},
    }
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
