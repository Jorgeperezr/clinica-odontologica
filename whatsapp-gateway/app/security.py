import hashlib
import hmac

from fastapi import Header, HTTPException, Request, status

from app.config import settings


def verify_internal_token(x_service_token: str = Header(default="")):
    """Protege /internal/* — solo Django (red interna del docker-compose) debe llamar aquí."""
    if x_service_token != settings.internal_service_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de servicio inválido.")


async def verify_meta_signature(request: Request):
    """
    Valida la firma X-Hub-Signature-256 que Meta envía en cada webhook,
    para asegurar que el payload realmente viene de Meta y no de un
    tercero que descubrió la URL pública (05-APIs, sección 13.3).
    """
    signature = request.headers.get("x-hub-signature-256", "")
    body = await request.body()
    expected = "sha256=" + hmac.new(
        settings.meta_app_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Firma de webhook inválida.")
