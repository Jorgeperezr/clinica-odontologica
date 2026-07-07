"""
whatsapp-gateway — microservicio FastAPI dedicado exclusivamente a la
integración con WhatsApp Business Cloud API (Meta). No contiene lógica
de negocio de la clínica: solo sabe enviar plantillas y procesar el
webhook, según lo definido en la Arquitectura v1.2 y en
05-APIs-Clinica-Odontologica.md, sección 13.
"""

import logging

from fastapi import Depends, FastAPI, Query, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse

from app.config import settings
from app.django_client import notify_django
from app.meta_client import send_template_message
from app.schemas import SendTemplateRequest, SendTemplateResponse
from app.security import verify_internal_token, verify_meta_signature

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="WhatsApp Gateway — Clínica Odontológica", version="1.0.0")


@app.get("/health", tags=["infra"])
async def health():
    return {"status": "ok"}


@app.post(
    "/internal/send-template",
    response_model=SendTemplateResponse,
    dependencies=[Depends(verify_internal_token)],
    tags=["internal"],
)
async def send_template(payload: SendTemplateRequest):
    """Llamado solo por Django/Celery (red interna) — 05-APIs, sección 13.1."""
    result = await send_template_message(
        to_phone=payload.to_phone,
        template_name=payload.template_name,
        language=payload.language,
        variables=payload.variables,
    )
    return SendTemplateResponse(**result)


@app.get("/whatsapp/webhook", tags=["webhook"])
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
):
    """Verificación inicial que exige Meta al registrar la URL del webhook."""
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_webhook_verify_token:
        return PlainTextResponse(hub_challenge)
    return JSONResponse({"detail": "Token de verificación inválido."}, status_code=status.HTTP_403_FORBIDDEN)


@app.post("/whatsapp/webhook", dependencies=[Depends(verify_meta_signature)], tags=["webhook"])
async def receive_webhook(request: Request):
    """
    Recibe eventos entrantes de Meta (mensajes, cambios de estado) y
    reenvía a Django solo lo relevante para el dominio (05-APIs, 13.2).
    """
    payload = await request.json()
    logger.info("Webhook de Meta recibido")

    for event in _parse_meta_events(payload):
        await notify_django(**event)

    return {"received": True}


def _parse_meta_events(payload: dict) -> list[dict]:
    """
    Traduce el formato de webhook de Meta a los eventos internos que
    Django entiende. Meta anida los datos en entry[].changes[].value.
    Devuelve una lista de dicts listos para notify_django().
    """
    events: list[dict] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})

            # Cambios de estado de mensajes que enviamos (sent/delivered/read/failed)
            for st in value.get("statuses", []):
                events.append({
                    "event_type": "message_status",
                    "provider_message_id": st.get("id", ""),
                    "status": st.get("status", ""),
                    "patient_phone": st.get("recipient_id", ""),
                    "raw_payload": st,
                })

            # Mensajes entrantes del paciente (ej. confirmación de cita)
            for msg in value.get("messages", []):
                text_body = ""
                if msg.get("type") == "text":
                    text_body = msg.get("text", {}).get("body", "")
                elif msg.get("type") == "button":
                    text_body = msg.get("button", {}).get("text", "")
                events.append({
                    "event_type": "inbound_message",
                    "patient_phone": msg.get("from", ""),
                    "text": text_body,
                    "provider_message_id": msg.get("id", ""),
                    "raw_payload": msg,
                })
    return events
