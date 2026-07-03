from typing import Any, Optional

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
    provider_message_id: Optional[str] = None
    detail: Optional[str] = None
