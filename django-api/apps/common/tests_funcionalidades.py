"""
Cada clínica ve lo que tiene contratado, y solo eso.

Lo que se comprueba aquí no es que el panel esconda un botón —eso es
cortesía— sino que la API rechace el módulo apagado. Sin eso, quien
conozca la URL, o quien tuviera la pestaña abierta cuando se apagó,
sigue usando algo que su clínica no tiene.
"""

from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.common.funcionalidades import CATALOGO, POR_DEFECTO, activa, normalizar
from apps.common.models import Tenant


class NormalizarTests(APITestCase):
    def test_rellena_lo_que_falta(self):
        # Una clínica creada antes de que existiera una funcionalidad la
        # recibe con su valor por defecto, sin migrar nada.
        salida = normalizar({"logros": False})
        self.assertEqual(set(salida), set(CATALOGO))
        self.assertFalse(salida["logros"])
        self.assertEqual(salida["inventario"], POR_DEFECTO["inventario"])

    def test_tira_lo_que_no_conoce(self):
        salida = normalizar({"inventado": True, "logros": True})
        self.assertNotIn("inventado", salida)

    def test_lo_que_no_es_un_diccionario_no_rompe(self):
        for basura in (None, [], "sí", 3):
            self.assertEqual(set(normalizar(basura)), set(CATALOGO))

    def test_whatsapp_viene_apagado_de_fabrica(self):
        # No funciona hasta que la clínica conecte su cuenta; encendido
        # sería un módulo que no manda nada y parece estropeado.
        self.assertFalse(POR_DEFECTO["whatsapp"])


class LaApiRechazaLoApagadoTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.tenant = Tenant.objects.create(
            name="Clínica Recortada", ruc="1790000095001",
            funcionalidades=normalizar({"logros": False, "inventario": False}))
        self.admin = User.objects.create_user(
            email="admin@recortada.ec", password="clave-larga-8gatos",
            role="admin", tenant=self.tenant)
        r = self.client.post("/api/v1/auth/login/",
                             {"email": self.admin.email, "password": "clave-larga-8gatos"},
                             format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")

    def test_logros_apagado_responde_403_aunque_sea_administrador(self):
        r = self.client.get("/api/v1/logros/")
        self.assertEqual(r.status_code, 403)
        self.assertIn("Rachas y logros", str(r.data))

    def test_inventario_apagado_tambien(self):
        r = self.client.get("/api/v1/inventory/products/")
        self.assertIn(r.status_code, (403, 404))

    def test_lo_que_sigue_encendido_funciona(self):
        # Apagar unos módulos no puede tumbar los demás.
        self.assertEqual(self.client.get("/api/v1/patients/").status_code, 200)

    def test_al_encenderlo_vuelve_a_funcionar_con_sus_datos(self):
        from apps.logros.models import Logro
        Logro.objects.create(tenant=self.tenant, nombre="Guardado", regla="manual")
        self.tenant.funcionalidades = normalizar({"logros": True})
        self.tenant.save(update_fields=["funcionalidades"])
        r = self.client.get("/api/v1/logros/")
        self.assertEqual(r.status_code, 200)
        # Apagar no borró nada.
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["nombre"], "Guardado")


class AltaDeClinicaConFuncionalidadesTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.dueno = User.objects.create_user(
            email="dueno@plataforma95.ec", password="clave-larga-8gatos",
            role="superadmin", tenant=None)
        self.client.force_authenticate(user=self.dueno)

    def test_se_eligen_al_crear(self):
        r = self.client.post("/api/v1/platform/clinics/", {
            "name": "Clínica A Medida", "ruc": "1790000095010",
            "funcionalidades": {"logros": True, "inventario": False},
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["funcionalidades"]["logros"])
        self.assertFalse(r.data["funcionalidades"]["inventario"])
        # Y las no mencionadas llegan con su valor por defecto.
        self.assertEqual(set(r.data["funcionalidades"]), set(CATALOGO))

    def test_sin_indicar_nada_se_usan_las_de_fabrica(self):
        r = self.client.post("/api/v1/platform/clinics/", {
            "name": "Clínica Estándar", "ruc": "1790000095011",
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["funcionalidades"], POR_DEFECTO)

    def test_se_pueden_cambiar_despues(self):
        r = self.client.post("/api/v1/platform/clinics/", {
            "name": "Clínica Cambiante", "ruc": "1790000095012",
        }, format="json")
        clinica = r.data["id"]
        r = self.client.patch(f"/api/v1/platform/clinics/{clinica}/",
                              {"funcionalidades": {"inventario": False}}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data["funcionalidades"]["inventario"])

    def test_una_clave_inventada_no_llega_a_la_base(self):
        r = self.client.post("/api/v1/platform/clinics/", {
            "name": "Clínica Rara", "ruc": "1790000095013",
            "funcionalidades": {"volar": True},
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertNotIn("volar", r.data["funcionalidades"])


class ActivaTests(APITestCase):
    def test_sin_clinica_no_hay_funcionalidad(self):
        # El Super Administrador no tiene tenant: estas rutas no son suyas.
        self.assertFalse(activa(None, "logros"))
