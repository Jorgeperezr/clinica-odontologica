from typing import Any

from pydantic import BaseModel


class SendTemplateRequest(BaseModel):
    to_phone: str
    template_name: str
    language: str = "es"
    variables: dict[str, str] = {}
    patient_id: str
    context: dict[str, Any] = {}


class SendTemplateResponse(BaseModel):
    status: str
    provider_message_id: str | None = None
    detail: str | None = None
