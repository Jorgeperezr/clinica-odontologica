"""Reporta eventos entrantes hacia Django (05-APIs, sección 13.2)."""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def notify_django(event_type: str, **payload):
    body = {"event_type": event_type, **payload}
    headers = {"X-Service-Token": settings.internal_service_token}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{settings.django_internal_url}/internal/whatsapp/events/",
                json=body,
                headers=headers,
            )
    except httpx.HTTPError as exc:
        logger.error("No se pudo notificar a Django: %s", exc)
