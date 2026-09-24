"""
Pruebas del gateway de WhatsApp (Sprint 69).

Este servicio no tenía ninguna, y es el que da la cara a internet: recibe
el webhook de Meta, valida su firma y traduce su formato al que entiende
Django. Un fallo aquí no se ve en el panel —se ve como recordatorios que
nunca llegan o confirmaciones de cita que se pierden—, así que conviene
que esté cubierto por pruebas y no por confianza.

Lo que se cubre, por orden de importancia:

  1. La FIRMA del webhook. Es lo único que separa un evento de Meta de
     uno inventado por cualquiera que descubra la URL pública.
  2. El PARSEO del formato de Meta, con sus anidamientos y sus campos
     ausentes. Meta manda cambios de estado y mensajes en la misma
     estructura, y omite claves con toda naturalidad.
  3. La verificación inicial de la URL y el token de servicio interno.
"""

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from main import _parse_meta_events, app

client = TestClient(app)


def firmar(body: bytes) -> str:
    """La misma firma que calcula Meta con el secreto de la aplicación."""
    return "sha256=" + hmac.new(
        settings.meta_app_secret.encode(), body, hashlib.sha256
    ).hexdigest()


def post_webhook(payload, firma=None):
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json",
               "X-Hub-Signature-256": firma if firma is not None else firmar(body)}
    return client.post("/whatsapp/webhook", content=body, headers=headers)


# ── 1. Firma ─────────────────────────────────────────────────────────
class TestFirmaDelWebhook:
    def test_firma_valida_se_acepta(self):
        resp = post_webhook({"entry": []})
        assert resp.status_code == 200
        assert resp.json() == {"received": True}

    def test_sin_firma_se_rechaza(self):
        resp = post_webhook({"entry": []}, firma="")
        assert resp.status_code == 401

    def test_firma_incorrecta_se_rechaza(self):
        resp = post_webhook({"entry": []}, firma="sha256=" + "0" * 64)
        assert resp.status_code == 401

    def test_firma_de_otro_cuerpo_se_rechaza(self):
        """Reenviar una firma válida con OTRO contenido no debe colar."""
        otra = firmar(json.dumps({"entry": [{"id": "distinto"}]}).encode())
        resp = post_webhook({"entry": []}, firma=otra)
        assert resp.status_code == 401


# ── 2. Parseo del formato de Meta ────────────────────────────────────
def _sobre(value):
    """Envoltorio entry[].changes[].value que usa Meta."""
    return {"entry": [{"id": "123", "changes": [{"value": value, "field": "messages"}]}]}


class TestParseoDeEventos:
    def test_mensaje_de_texto(self):
        eventos = _parse_meta_events(_sobre({
            "messages": [{
                "from": "593999123456", "id": "wamid.ABC", "type": "text",
                "text": {"body": "CONFIRMO"},
            }],
        }))
        assert len(eventos) == 1
        ev = eventos[0]
        assert ev["event_type"] == "inbound_message"
        assert ev["patient_phone"] == "593999123456"
        assert ev["text"] == "CONFIRMO"
        assert ev["provider_message_id"] == "wamid.ABC"

    def test_respuesta_por_boton(self):
        """La plantilla de recordatorio se responde con un botón, no con texto."""
        eventos = _parse_meta_events(_sobre({
            "messages": [{
                "from": "593999123456", "id": "wamid.BTN", "type": "button",
                "button": {"text": "Sí, confirmo", "payload": "CONFIRMAR"},
            }],
        }))
        assert eventos[0]["text"] == "Sí, confirmo"
        assert eventos[0]["event_type"] == "inbound_message"

    def test_cambio_de_estado(self):
        eventos = _parse_meta_events(_sobre({
            "statuses": [{
                "id": "wamid.XYZ", "status": "delivered", "recipient_id": "593999123456",
            }],
        }))
        assert len(eventos) == 1
        assert eventos[0]["event_type"] == "message_status"
        assert eventos[0]["status"] == "delivered"
        assert eventos[0]["provider_message_id"] == "wamid.XYZ"
        assert eventos[0]["patient_phone"] == "593999123456"

    def test_estados_y_mensajes_en_el_mismo_sobre(self):
        """Meta los manda juntos; hay que devolver los dos, no el primero."""
        eventos = _parse_meta_events(_sobre({
            "statuses": [{"id": "s1", "status": "read", "recipient_id": "593999"}],
            "messages": [{"from": "593999", "id": "m1", "type": "text",
                          "text": {"body": "hola"}}],
        }))
        tipos = [e["event_type"] for e in eventos]
        assert tipos == ["message_status", "inbound_message"]

    def test_varios_entry_y_varios_changes(self):
        payload = {"entry": [
            {"changes": [{"value": {"statuses": [{"id": "a", "status": "sent"}]}},
                         {"value": {"statuses": [{"id": "b", "status": "sent"}]}}]},
            {"changes": [{"value": {"messages": [
                {"from": "1", "id": "c", "type": "text", "text": {"body": "x"}}]}}]},
        ]}
        assert len(_parse_meta_events(payload)) == 3

    @pytest.mark.parametrize("tipo,cuerpo", [
        ("image", {"image": {"id": "img1"}}),
        ("audio", {"audio": {"id": "aud1"}}),
        ("location", {"location": {"latitude": 0, "longitude": 0}}),
    ])
    def test_tipos_no_textuales_no_rompen(self, tipo, cuerpo):
        """
        El paciente puede mandar una foto. No hay texto que interpretar,
        pero el evento debe llegar igual: perderlo dejaría la conversación
        sin registro en la historia.
        """
        eventos = _parse_meta_events(_sobre({
            "messages": [{"from": "593999", "id": "wamid.X", "type": tipo, **cuerpo}],
        }))
        assert len(eventos) == 1
        assert eventos[0]["text"] == ""
        assert eventos[0]["raw_payload"]["type"] == tipo

    @pytest.mark.parametrize("payload", [
        {},
        {"entry": []},
        {"entry": [{}]},
        {"entry": [{"changes": []}]},
        {"entry": [{"changes": [{}]}]},
        {"entry": [{"changes": [{"value": {}}]}]},
        {"object": "whatsapp_business_account"},
    ])
    def test_sobres_vacios_o_incompletos_no_rompen(self, payload):
        """Meta omite claves con naturalidad; ninguna debe provocar KeyError."""
        assert _parse_meta_events(payload) == []

    def test_campos_ausentes_no_rompen_el_evento(self):
        """Un mensaje sin `from` ni `id` sale con cadenas vacías, no revienta."""
        eventos = _parse_meta_events(_sobre({"messages": [{"type": "text"}]}))
        assert eventos[0]["patient_phone"] == ""
        assert eventos[0]["provider_message_id"] == ""
        assert eventos[0]["text"] == ""

    def test_se_conserva_el_payload_original(self):
        """El crudo se guarda para poder depurar un caso raro más adelante."""
        msg = {"from": "593999", "id": "m1", "type": "text",
               "text": {"body": "hola"}, "timestamp": "1700000000"}
        eventos = _parse_meta_events(_sobre({"messages": [msg]}))
        assert eventos[0]["raw_payload"] == msg


# ── 3. Verificación de la URL y token interno ────────────────────────
class TestVerificacionYTokenInterno:
    def test_verificacion_correcta_devuelve_el_desafio(self):
        resp = client.get("/whatsapp/webhook", params={
            "hub.mode": "subscribe",
            "hub.verify_token": settings.meta_webhook_verify_token,
            "hub.challenge": "1234567890",
        })
        assert resp.status_code == 200
        assert resp.text == "1234567890"

    def test_token_de_verificacion_incorrecto(self):
        resp = client.get("/whatsapp/webhook", params={
            "hub.mode": "subscribe", "hub.verify_token": "otro", "hub.challenge": "x",
        })
        assert resp.status_code == 403

    def test_modo_distinto_de_subscribe(self):
        resp = client.get("/whatsapp/webhook", params={
            "hub.mode": "unsubscribe",
            "hub.verify_token": settings.meta_webhook_verify_token,
            "hub.challenge": "x",
        })
        assert resp.status_code == 403

    def test_envio_interno_exige_token_de_servicio(self):
        resp = client.post("/internal/send-template", json={
            "to_phone": "593999", "template_name": "recordatorio_cita",
            "patient_id": "p1",
        })
        assert resp.status_code == 401

    def test_envio_interno_con_token_incorrecto(self):
        resp = client.post("/internal/send-template",
                           headers={"X-Service-Token": "no-es"},
                           json={"to_phone": "593999", "template_name": "x", "patient_id": "p1"})
        assert resp.status_code == 401

    def test_health(self):
        assert client.get("/health").json() == {"status": "ok"}


# ── 4. Recorrido completo ────────────────────────────────────────────
class TestDelWebhookAlAviso:
    """
    Que el parseo funcione no basta: hay que comprobar que lo que sale de
    él llega de verdad a Django. Es la costura donde un `for` mal puesto
    no da error y simplemente no avisa a nadie.
    """

    def test_cada_evento_se_notifica_a_django(self, monkeypatch):
        recibidos = []

        async def falso_notify(**kwargs):
            recibidos.append(kwargs)

        import main
        monkeypatch.setattr(main, "notify_django", falso_notify)

        resp = post_webhook(_sobre({
            "statuses": [{"id": "s1", "status": "delivered", "recipient_id": "593999"}],
            "messages": [{"from": "593999", "id": "m1", "type": "text",
                          "text": {"body": "CONFIRMO"}}],
        }))

        assert resp.status_code == 200
        assert [e["event_type"] for e in recibidos] == ["message_status", "inbound_message"]
        assert recibidos[1]["text"] == "CONFIRMO"

    def test_un_evento_que_falla_no_tumba_la_respuesta(self, monkeypatch):
        """
        Meta reintenta ante un 5xx y acaba desactivando el webhook de la
        cuenta. Que un evento falle no debe provocar eso: se pierde ese
        evento, que es malo, pero no el webhook, que sería peor.
        """
        async def revienta(**kwargs):
            raise RuntimeError("fallo inesperado")

        import main
        monkeypatch.setattr(main, "notify_django", revienta)

        resp = post_webhook(_sobre({"messages": [
            {"from": "1", "id": "m", "type": "text", "text": {"body": "x"}}]}))
        assert resp.status_code == 200

    def test_un_evento_roto_no_impide_procesar_los_demas(self, monkeypatch):
        """Si el primero falla, el segundo tiene que llegar igualmente."""
        vistos = []

        async def falla_el_primero(**kwargs):
            if not vistos:
                vistos.append("fallo")
                raise RuntimeError("fallo inesperado")
            vistos.append(kwargs["event_type"])

        import main
        monkeypatch.setattr(main, "notify_django", falla_el_primero)

        resp = post_webhook(_sobre({
            "statuses": [{"id": "s1", "status": "sent", "recipient_id": "1"}],
            "messages": [{"from": "1", "id": "m", "type": "text", "text": {"body": "x"}}],
        }))
        assert resp.status_code == 200
        assert vistos == ["fallo", "inbound_message"]
