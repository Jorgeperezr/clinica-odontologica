"""
Cada clínica envía desde SU cuenta de WhatsApp.

Lo que se comprueba es a qué número de Meta va la petición y con qué
token. Si eso se equivoca, el mensaje sale desde un número que el
paciente no reconoce, firmado como si fuera su clínica: es el fallo que
más caro sale de todo este módulo, porque se descubre cuando alguien
responde al número equivocado.

Se prueba por el endpoint de verdad y con `TestClient`, como el resto de
las pruebas de este servicio, en vez de llamar a la corrutina a mano:
así se cubre también que el esquema acepte el campo nuevo.
"""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from main import app

client = TestClient(app)

RUTA = "/internal/send-template"
CABECERAS = {"X-Service-Token": settings.internal_service_token}

PETICION = {
    "to_phone": "+593999111222",
    "template_name": "recordatorio_cita",
    "language": "es",
    "variables": {"1": "Ana"},
    "patient_id": "11111111-1111-1111-1111-111111111111",
}


class _RespuestaFalsa:
    status_code = 200

    @staticmethod
    def json():
        return {"messages": [{"id": "wamid.PRUEBA"}]}

    @staticmethod
    def raise_for_status():
        return None


@pytest.fixture
def espia(monkeypatch):
    """Intercepta la llamada a Meta y guarda a dónde iba."""
    visto = {}

    class ClienteFalso:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None, **kw):
            visto["url"] = url
            visto["headers"] = headers or {}
            return _RespuestaFalsa()

    monkeypatch.setattr(httpx, "AsyncClient", ClienteFalso)
    # Sin esto, el cliente detecta «sin credenciales» y simula el envío
    # sin llegar a llamar a nadie, con lo que la prueba no probaría nada.
    monkeypatch.setattr(settings, "meta_access_token", "TOKEN_PLATAFORMA")
    monkeypatch.setattr(settings, "meta_phone_number_id", "NUMERO_PLATAFORMA")
    return visto


class TestCadaClinicaConLoSuyo:
    def test_con_credenciales_sale_de_la_cuenta_de_la_clinica(self, espia):
        cuerpo = dict(PETICION)
        cuerpo["credenciales"] = {
            "phone_number_id": "NUMERO_DE_LA_CLINICA",
            "access_token": "TOKEN_DE_LA_CLINICA",
        }
        r = client.post(RUTA, json=cuerpo, headers=CABECERAS)
        assert r.status_code == 200, r.text
        assert "NUMERO_DE_LA_CLINICA" in espia["url"]
        assert espia["headers"]["Authorization"] == "Bearer TOKEN_DE_LA_CLINICA"
        # Y NO se usó la de la plataforma.
        assert "NUMERO_PLATAFORMA" not in espia["url"]

    def test_sin_credenciales_sale_de_la_plataforma(self, espia):
        # Es el caso del código OTP: llega antes de que nadie haya dicho
        # de qué clínica es, así que no hay cuenta de clínica que usar.
        r = client.post(RUTA, json=PETICION, headers=CABECERAS)
        assert r.status_code == 200, r.text
        assert "NUMERO_PLATAFORMA" in espia["url"]
        assert espia["headers"]["Authorization"] == "Bearer TOKEN_PLATAFORMA"

    def test_el_token_de_la_clinica_no_aparece_en_la_respuesta(self, espia):
        cuerpo = dict(PETICION)
        cuerpo["credenciales"] = {
            "phone_number_id": "NUMERO_DE_LA_CLINICA",
            "access_token": "TOKEN_SECRETISIMO_DE_LA_CLINICA",
        }
        r = client.post(RUTA, json=cuerpo, headers=CABECERAS)
        assert "TOKEN_SECRETISIMO_DE_LA_CLINICA" not in r.text
