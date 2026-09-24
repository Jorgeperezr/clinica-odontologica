"""
Cada clínica conecta su propia cuenta de WhatsApp.

Lo que más se comprueba aquí es lo que NO tiene que pasar: que el token
vuelva al panel. Es una credencial que permite enviar mensajes en nombre
de la clínica; devolverla al navegador la expone a cualquier extensión
instalada y a cualquiera que mire la pestaña de red.
"""

from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.common.funcionalidades import normalizar
from apps.common.models import Tenant
from apps.whatsapp.models import ConfiguracionWhatsApp

TOKEN = "EAAG1234muyLargoYSecreto567890abcdef"
RUTA = "/api/v1/config/whatsapp/"


class Base(APITestCase):
    def setUp(self):
        cache.clear()
        self.tenant = Tenant.objects.create(
            name="Clínica WA", ruc="1790000096001",
            funcionalidades=normalizar({"whatsapp": True}))
        self.admin = User.objects.create_user(
            email="admin@wa.ec", password="clave-larga-8gatos",
            role="admin", tenant=self.tenant)
        self.doctor = User.objects.create_user(
            email="doc@wa.ec", password="clave-larga-8gatos",
            role="doctor", tenant=self.tenant)
        self.entrar(self.admin)

    def entrar(self, usuario):
        r = self.client.post("/api/v1/auth/login/",
                             {"email": usuario.email, "password": "clave-larga-8gatos"},
                             format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")

    def configurar(self):
        return self.client.patch(RUTA, {
            "phone_number_id": "123456789",
            "numero_visible": "+593999111222",
            "access_token": TOKEN,
            "plantilla_recordatorio": "recordatorio_cita",
        }, format="json")


class ElTokenEntraPeroNoSaleTests(Base):
    def test_al_guardarlo_no_vuelve_en_la_respuesta(self):
        r = self.configurar()
        self.assertEqual(r.status_code, 200, r.data)
        self.assertNotIn(TOKEN, str(r.data))
        self.assertTrue(r.data["token_puesto"])

    def test_al_leer_tampoco(self):
        self.configurar()
        r = self.client.get(RUTA)
        self.assertNotIn(TOKEN, str(r.data))
        self.assertNotIn("access_token", r.data)

    def test_se_da_una_pista_para_reconocerlo(self):
        self.configurar()
        r = self.client.get(RUTA)
        self.assertEqual(r.data["token_pista"], "…cdef")
        # Y la pista no basta para reconstruirlo.
        self.assertNotIn(TOKEN[:-4], str(r.data))

    def test_en_la_base_esta_cifrado(self):
        self.configurar()
        obj = ConfiguracionWhatsApp.objects.get(tenant=self.tenant)
        self.assertNotIn(TOKEN, obj.access_token_cifrado)
        self.assertEqual(obj.token, TOKEN)


class NoSeBorraSinQuererTests(Base):
    def test_mandar_el_token_vacio_no_lo_borra(self):
        # Un formulario que reenvía sus campos vacíos dejaría a la
        # clínica sin WhatsApp sin que nadie lo pidiera.
        self.configurar()
        r = self.client.patch(RUTA, {"access_token": "", "numero_visible": "+593"},
                              format="json")
        self.assertTrue(r.data["token_puesto"])

    def test_para_borrarlo_hay_que_decirlo(self):
        self.configurar()
        r = self.client.patch(RUTA, {"token_borrar": True}, format="json")
        self.assertFalse(r.data["token_puesto"])
        self.assertFalse(r.data["activo"])


class EncenderYApagarTests(Base):
    def test_no_se_puede_encender_a_medio_configurar(self):
        r = self.client.patch(RUTA, {"activo": True}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Faltan datos", str(r.data))

    def test_configurado_si_se_puede(self):
        self.configurar()
        r = self.client.patch(RUTA, {"activo": True}, format="json")
        self.assertTrue(r.data["activo"])
        self.assertTrue(r.data["puede_enviar"])

    def test_borrar_el_token_lo_apaga(self):
        # Si no, la clínica quedaría «encendida» sin poder enviar nada, y
        # los recordatorios fallarían en silencio.
        self.configurar()
        self.client.patch(RUTA, {"activo": True}, format="json")
        r = self.client.patch(RUTA, {"token_borrar": True}, format="json")
        self.assertFalse(r.data["activo"])
        self.assertFalse(r.data["puede_enviar"])


class QuienPuedeConfigurarTests(Base):
    def test_un_doctor_sin_permiso_no(self):
        self.entrar(self.doctor)
        self.assertEqual(self.client.get(RUTA).status_code, 403)

    def test_un_doctor_con_permiso_si(self):
        # Ahora es una función del profesional (apps/accounts/funciones.py).
        self.doctor.funciones = {"whatsapp": True}
        self.doctor.save(update_fields=["funciones"])
        self.entrar(self.doctor)
        self.assertEqual(self.client.get(RUTA).status_code, 200)


class SinLaFuncionalidadNoHayNadaTests(APITestCase):
    def test_una_clinica_sin_whatsapp_contratado_recibe_403(self):
        cache.clear()
        tenant = Tenant.objects.create(
            name="Clínica Sin WA", ruc="1790000096009",
            funcionalidades=normalizar({"whatsapp": False}))
        admin = User.objects.create_user(
            email="admin@sinwa.ec", password="clave-larga-8gatos",
            role="admin", tenant=tenant)
        r = self.client.post("/api/v1/auth/login/",
                             {"email": admin.email, "password": "clave-larga-8gatos"},
                             format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        resp = self.client.get(RUTA)
        self.assertEqual(resp.status_code, 403)
        self.assertIn("WhatsApp", str(resp.data))


class NoSeVeLaDeOtraClinicaTests(Base):
    def test_cada_clinica_tiene_la_suya(self):
        self.configurar()
        otra = Tenant.objects.create(
            name="Otra WA", ruc="1790000096020",
            funcionalidades=normalizar({"whatsapp": True}))
        admin2 = User.objects.create_user(
            email="admin@otrawa.ec", password="clave-larga-8gatos",
            role="admin", tenant=otra)
        self.entrar(admin2)
        r = self.client.get(RUTA)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["token_puesto"])
        self.assertEqual(r.data["phone_number_id"], "")
