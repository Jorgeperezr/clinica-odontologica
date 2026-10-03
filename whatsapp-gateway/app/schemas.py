from typing import Any

from pydantic import BaseModel


class CredencialesDeClinica(BaseModel):
    """
    Las de la clínica que envía, cuando las trae.

    Viajan en la petición interna en vez de que el gateway lea la base
    de Django: eso sería un acoplamiento mucho peor y obligaría a este
    servicio a conocer el modelo de datos de la otra mitad.
    """

    phone_number_id: str
    access_token: str


class SendTemplateRequest(BaseModel):
    to_phone: str
    template_name: str
    language: str = "es"
    variables: dict[str, str] = {}
    patient_id: str
    context: dict[str, Any] = {}
    # Sin credenciales se usan las del gateway, que es el caso del
    # código OTP: llega antes de saber de qué clínica es nadie.
    credenciales: CredencialesDeClinica | None = None


class SendTemplateResponse(BaseModel):
    status: str
    provider_message_id: str | None = None
    detail: str | None = None
