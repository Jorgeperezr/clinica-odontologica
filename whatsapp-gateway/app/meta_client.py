"""
Único punto del sistema que le habla directamente a la WhatsApp
Business Cloud API de Meta (Arquitectura v1.2, sección 4 "Integración
con WhatsApp Cloud API"). Django/Celery nunca llaman a Meta directo.
"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def send_template_message(to_phone: str, template_name: str, language: str, variables: dict) -> dict:
    if not settings.meta_access_token or not settings.meta_phone_number_id:
        # Modo desarrollo sin credenciales reales de Meta todavía configuradas.
        logger.warning("META_ACCESS_TOKEN no configurado — envío simulado (modo dev).")
        return {"status": "queued", "provider_message_id": "dev-simulated"}

    url = (
        f"https://graph.facebook.com/{settings.meta_api_version}/"
        f"{settings.meta_phone_number_id}/messages"
    )
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": value} for value in variables.values()
                    ],
                }
            ],
        },
    }
    headers = {"Authorization": f"Bearer {settings.meta_access_token}"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=payload, headers=headers)

    if response.status_code >= 400:
        logger.error("Error de Meta al enviar plantilla: %s", response.text)
        return {"status": "error", "detail": response.text}

    data = response.json()
    message_id = data.get("messages", [{}])[0].get("id")
    return {"status": "sent", "provider_message_id": message_id}
