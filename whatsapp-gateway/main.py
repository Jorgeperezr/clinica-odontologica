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
    Recibe eventos entrantes de Meta (mensajes, cambios de estado).
    Reenvía a Django solo lo relevante para el dominio (05-APIs, 13.2).

    Implementación completa del parseo de eventos programada para el
    Sprint 10 del Roadmap; aquí queda el esqueleto validado por firma.
    """
    payload = await request.json()
    logger.info("Webhook de Meta recibido: %s", payload)

    # TODO (Sprint 10): parsear `payload["entry"]` según el formato de
    # Meta y llamar a notify_django(event_type=..., ...) por cada
    # mensaje de estado o respuesta entrante relevante. Se deja el
    # llamado de ejemplo comentado como referencia del contrato:
    # await notify_django(
    #     event_type="message_status",
    #     patient_phone="...",
    #     provider_message_id="...",
    #     status="delivered",
    #     raw_payload=payload,
    # )

    return {"received": True}
