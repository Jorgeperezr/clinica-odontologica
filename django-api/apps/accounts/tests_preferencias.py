"""
Preferencias propias del profesional: por ahora, usar o no el
odontograma 3D.

Lo que se fija:
  - que cada cual cambie las suyas y SOLO las suyas;
  - que `/auth/me/` las devuelva, que es de donde las lee el panel;
  - que se diga si tienen efecto en la clínica (una preferencia sobre
    algo que la clínica no tiene contratado no hace nada, y el panel
    tiene que poder explicarlo);
  - que no se cuele nada que no sea una preferencia conocida.
"""

from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.common.funcionalidades import normalizar
from apps.common.models import Tenant

RUTA = "/api/v1/auth/me/preferencias/"


class PreferenciasTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Pref", ruc="1790000098001")
        self.doctor = User.objects.create_user(
            email="doc@pref.ec", password="clave-larga-8gatos", role="doctor", tenant=self.tenant)
        self.otro = User.objects.create_user(
            email="otro@pref.ec", password="clave-larga-8gatos", role="doctor", tenant=self.tenant)
        self.client.force_authenticate(user=self.doctor)

    def test_por_defecto_el_3d_esta_encendido_y_disponible(self):
        r = self.client.get(RUTA)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["preferencias"], {"odontograma_3d": True})
        self.assertEqual(r.data["disponibles"], {"odontograma_3d": True})

    def test_apagarlo_se_guarda_y_lo_ve_auth_me(self):
        r = self.client.patch(RUTA, {"odontograma_3d": False}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data["preferencias"]["odontograma_3d"])
        self.doctor.refresh_from_db()
        self.assertEqual(self.doctor.preferencias, {"odontograma_3d": False})
        self.assertFalse(self.client.get("/api/v1/auth/me/").data["preferencias"]["odontograma_3d"])

    def test_no_toca_las_de_otro(self):
        self.client.patch(RUTA, {"odontograma_3d": False}, format="json")
        self.otro.refresh_from_db()
        self.assertEqual(self.otro.preferencias, {})
        self.client.force_authenticate(user=self.otro)
        self.assertTrue(self.client.get(RUTA).data["preferencias"]["odontograma_3d"])

    def test_si_la_clinica_no_lo_tiene_se_dice(self):
        self.tenant.funcionalidades = normalizar({"odontograma_3d": False})
        self.tenant.save(update_fields=["funcionalidades"])
        r = self.client.get(RUTA)
        self.assertFalse(r.data["disponibles"]["odontograma_3d"])

    def test_claves_desconocidas_se_rechazan(self):
        r = self.client.patch(RUTA, {"es_admin": True}, format="json")
        self.assertEqual(r.status_code, 400)
        self.doctor.refresh_from_db()
        self.assertEqual(self.doctor.preferencias, {})

    def test_solo_verdadero_o_falso(self):
        r = self.client.patch(RUTA, {"odontograma_3d": "no"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_un_paciente_no_tiene_preferencias_de_panel(self):
        paciente = User.objects.create_user(
            email="pac@pref.ec", password="clave-larga-8gatos", role="patient", tenant=self.tenant)
        self.client.force_authenticate(user=paciente)
        self.assertEqual(self.client.get(RUTA).status_code, 403)
        self.assertEqual(self.client.patch(RUTA, {"odontograma_3d": False}, format="json").status_code, 403)

    def test_sin_sesion_no_hay_acceso(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(RUTA).status_code, 401)
