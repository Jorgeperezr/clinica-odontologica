"""
Dos llaves para cada módulo: la plataforma decide qué tiene contratado
la clínica y la administración de la clínica, qué quiere usar.

Se fija: que la clínica pueda apagar el odontograma 3D y las rachas y
logros; que apagarlos cierre también la API (no solo el menú); que no
pueda encender lo que la plataforma no le dio; y que otra persona que
no sea su administración no pueda tocarlo.
"""

from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.common.funcionalidades import activa, efectivas, normalizar
from apps.common.models import Tenant

URL = "/api/v1/config/modulos/"


class ModulosDeLaClinica(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Clínica Módulos", funcionalidades=normalizar({"inventario": False}))
        self.admin = User.objects.create_user(email="admin@mod.ec", password="superseguro123",
                                              role="admin", tenant=self.tenant)
        self.doctor = User.objects.create_user(email="doc@mod.ec", password="superseguro123",
                                               role="doctor", tenant=self.tenant)

    def estado(self):
        self.client.force_authenticate(self.admin)
        return {m["clave"]: m for m in self.client.get(URL).data}

    def test_la_clinica_apaga_el_3d_y_los_logros(self):
        self.client.force_authenticate(self.admin)
        r = self.client.patch(URL, {"odontograma_3d": False, "logros": False}, format="json")
        self.assertEqual(r.status_code, 200)
        self.tenant.refresh_from_db()
        self.assertFalse(activa(self.tenant, "odontograma_3d"))
        self.assertFalse(activa(self.tenant, "logros"))
        # Sigue contratado: si lo vuelve a encender, está ahí.
        m = self.estado()
        self.assertTrue(m["logros"]["contratado"])
        self.assertFalse(m["logros"]["activo"])
        self.client.patch(URL, {"logros": True}, format="json")
        self.tenant.refresh_from_db()
        self.assertTrue(activa(self.tenant, "logros"))

    def test_el_perfil_del_panel_lo_refleja(self):
        self.client.force_authenticate(self.admin)
        self.client.patch(URL, {"odontograma_3d": False}, format="json")
        self.client.force_authenticate(self.doctor)
        perfil = self.client.get("/api/v1/auth/me/").data
        self.assertFalse(perfil["funcionalidades"]["odontograma_3d"])

    def test_apagado_cierra_tambien_la_api(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get("/api/v1/logros/").status_code, 200)
        self.client.patch(URL, {"logros": False}, format="json")
        self.assertEqual(self.client.get("/api/v1/logros/").status_code, 403)

    def test_no_puede_encender_lo_no_contratado(self):
        self.client.force_authenticate(self.admin)
        r = self.client.patch(URL, {"inventario": True}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertIn("Inventario", r.data["detail"])
        self.assertFalse(efectivas(self.tenant)["inventario"])

    def test_solo_su_administracion(self):
        self.client.force_authenticate(self.doctor)
        self.assertEqual(self.client.patch(URL, {"logros": False}, format="json").status_code, 403)

    def test_valores_raros(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.patch(URL, {"nada": False}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(URL, {"logros": "no"}, format="json").status_code, 400)

    def test_la_plataforma_apaga_aunque_la_clinica_lo_quiera(self):
        self.tenant.modulos_clinica = {"logros": True}
        self.tenant.funcionalidades = normalizar({"logros": False})
        self.tenant.save()
        self.assertFalse(activa(self.tenant, "logros"))
