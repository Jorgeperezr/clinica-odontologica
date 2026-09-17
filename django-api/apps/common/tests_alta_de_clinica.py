"""
Dar de alta una clínica y entregarle sus credenciales (Sprint 92).

Antes esto eran TRES actos en dos pestañas del panel: crear la clínica,
ir a «Administradores» a crear su admin —inventándose el Super
Administrador una contraseña a mano— y, si se quería una decente,
restablecerla para obtener una generada.

Dos cosas estaban mal, y la segunda importa más:

  1. Pedirle a una persona que invente un secreto para otra es como se
     acaban poniendo contraseñas como «clinica2026».

  2. **Esa contraseña no caducaba.** El dueño de la plataforma la conocía
     y seguía siendo válida para siempre, así que conservaba
     indefinidamente la llave de los datos clínicos de esa clínica.
     «Entregar las credenciales» no entregaba nada.

Lo que se fija aquí es que la entrega sea una entrega.
"""

from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.common.models import Tenant


class AltaDeClinicaEnUnSoloPasoTests(APITestCase):
    def setUp(self):
        self.dueno = User.objects.create_user(
            email="dueno@plataforma.ec", password="superseguro123",
            role="superadmin", tenant=None,
        )
        self.client.force_authenticate(user=self.dueno)

    def test_crear_clinica_con_su_administrador_devuelve_las_credenciales(self):
        r = self.client.post("/api/v1/platform/clinics/", {
            "name": "Clínica Nueva", "ruc": "1790000092001",
            "admin_email": "admin@nueva.ec", "admin_full_name": "Lucía Mora",
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIn("admin", r.data)
        self.assertEqual(r.data["admin"]["email"], "admin@nueva.ec")
        self.assertTrue(r.data["admin"]["temporary_password"])

        admin = User.objects.get(email="admin@nueva.ec")
        self.assertEqual(admin.role, "admin")
        self.assertEqual(admin.tenant.name, "Clínica Nueva")
        self.assertTrue(admin.check_password(r.data["admin"]["temporary_password"]))
        self.assertTrue(admin.must_change_password)

    def test_la_contrasena_no_la_inventa_nadie(self):
        """Dos altas seguidas no pueden dar la misma contraseña."""
        claves = set()
        for i in (1, 2):
            r = self.client.post("/api/v1/platform/clinics/", {
                "name": f"Clínica {i}", "ruc": f"179000009200{i+1}",
                "admin_email": f"a{i}@nueva.ec", "admin_full_name": f"A{i}",
            }, format="json")
            claves.add(r.data["admin"]["temporary_password"])
        self.assertEqual(len(claves), 2)
        self.assertTrue(all(len(k) >= 12 for k in claves))

    def test_se_puede_crear_la_clinica_sin_administrador_como_siempre(self):
        r = self.client.post("/api/v1/platform/clinics/", {
            "name": "Clínica Sola", "ruc": "1790000092009",
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        # `admin` es un campo de siempre del serializador (sale None cuando
        # no hay ninguno); lo que se comprueba es que no se entregue
        # ninguna credencial cuando nadie la pidió.
        self.assertIsNone(r.data["admin"])
        self.assertTrue(Tenant.objects.filter(name="Clínica Sola").exists())

    def test_un_correo_repetido_no_deshace_la_clinica(self):
        """
        La clínica ya está creada cuando se detecta: cancelarla entera por
        un correo repetido sería peor que avisar.
        """
        User.objects.create_user(email="repetido@x.ec", password="superseguro123",
                                 role="admin", tenant=None)
        r = self.client.post("/api/v1/platform/clinics/", {
            "name": "Clínica Choque", "ruc": "1790000092010",
            "admin_email": "repetido@x.ec", "admin_full_name": "Otro",
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIn("error", r.data["admin"])
        self.assertTrue(Tenant.objects.filter(name="Clínica Choque").exists())


class LaEntregaDeCredencialesEsDeVerdadTests(APITestCase):
    """
    La mitad que importa: mientras la contraseña sea la que puso otro, la
    cuenta no puede hacer nada más que cambiarla.

    Aquí se inicia sesión DE VERDAD, pidiendo el token a `/auth/login/`,
    en vez de usar `force_authenticate`. No es purismo: el candado vive en
    la clase de autenticación, y `force_authenticate` se salta la
    autenticación entera por diseño, así que con él estos tests pasarían
    sin comprobar nada. Con el token de verdad se recorre el mismo camino
    que recorre el panel.
    """

    TEMPORAL = "temporal-de-fabrica-123"

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Entrega", ruc="1790000092020")
        self.admin = User.objects.create_user(
            email="admin@entrega.ec", password=self.TEMPORAL,
            role="admin", tenant=self.tenant,
        )
        self.admin.must_change_password = True
        self.admin.save(update_fields=["must_change_password"])
        self.entrar("admin@entrega.ec", self.TEMPORAL)

    def entrar(self, email, password):
        """Inicia sesión como lo hace el panel y deja el token puesto."""
        r = self.client.post("/api/v1/auth/login/",
                             {"email": email, "password": password}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        return r

    def test_con_la_temporal_se_puede_entrar_pero_avisando(self):
        """
        Entrar tiene que funcionar —si no, no habría forma de cambiarla—,
        pero la respuesta debe decir que hay algo pendiente para que el
        panel lleve a cambiarla en vez de al escritorio.
        """
        r = self.entrar("admin@entrega.ec", self.TEMPORAL)
        self.assertTrue(r.data["must_change_password"])

    def test_con_contrasena_temporal_no_se_puede_operar(self):
        for ruta in ("/api/v1/patients/", "/api/v1/users/", "/api/v1/reports/financial/"):
            r = self.client.get(ruta)
            self.assertEqual(r.status_code, 403, f"{ruta} respondió {r.status_code}")
            self.assertEqual(r.data["error"]["code"], "password_change_required", ruta)

    def test_pero_si_se_puede_saber_quien_es_uno_y_cambiarla(self):
        r = self.client.get("/api/v1/auth/me/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["must_change_password"])

    def test_al_elegir_la_suya_se_desbloquea(self):
        r = self.client.post("/api/v1/auth/change-password/",
                             {"new_password": "mi-clave-elegida-9animales"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.must_change_password)
        self.assertTrue(self.admin.check_password("mi-clave-elegida-9animales"))
        # Con el MISMO token de antes: el candado lo levanta haber
        # cambiado la contraseña, no volver a iniciar sesión.
        self.assertEqual(self.client.get("/api/v1/patients/").status_code, 200)

    def test_la_temporal_deja_de_servir_para_entrar(self):
        """
        Lo que el Super Administrador conocía ya no abre nada: eso es lo
        que convierte la entrega en una entrega.
        """
        self.client.post("/api/v1/auth/change-password/",
                         {"new_password": "mi-clave-elegida-9animales"}, format="json")
        r = self.client.post("/api/v1/auth/login/",
                             {"email": "admin@entrega.ec", "password": self.TEMPORAL},
                             format="json")
        self.assertEqual(r.status_code, 401)

    def test_no_vale_repetir_la_temporal(self):
        """
        Si valiera, quien la entregó seguiría conociéndola: el cambio
        obligatorio no habría servido de nada.
        """
        r = self.client.post("/api/v1/auth/change-password/",
                             {"new_password": self.TEMPORAL}, format="json")
        self.assertEqual(r.status_code, 400)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.must_change_password)

    def test_no_vale_una_contrasena_debil(self):
        r = self.client.post("/api/v1/auth/change-password/",
                             {"new_password": "12345678"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_quien_no_tiene_contrasena_temporal_debe_dar_la_actual(self):
        User.objects.create_user(
            email="normal@entrega.ec", password="la-de-siempre-8leones",
            role="admin", tenant=self.tenant,
        )
        self.entrar("normal@entrega.ec", "la-de-siempre-8leones")
        r = self.client.post("/api/v1/auth/change-password/",
                             {"new_password": "otra-distinta-7tigres"}, format="json")
        self.assertEqual(r.status_code, 400, "dejó cambiarla sin pedir la actual")

        r = self.client.post("/api/v1/auth/change-password/", {
            "current_password": "la-de-siempre-8leones",
            "new_password": "otra-distinta-7tigres",
        }, format="json")
        self.assertEqual(r.status_code, 200, r.data)


class RestablecerTambienObligaACambiarTests(APITestCase):
    def setUp(self):
        self.dueno = User.objects.create_user(
            email="dueno2@plataforma.ec", password="superseguro123",
            role="superadmin", tenant=None,
        )
        self.tenant = Tenant.objects.create(name="Clínica Reset", ruc="1790000092030")
        self.admin = User.objects.create_user(
            email="admin@reset.ec", password="la-suya-de-antes-5", role="admin",
            tenant=self.tenant,
        )
        self.client.force_authenticate(user=self.dueno)

    def test_restablecer_deja_la_cuenta_pendiente_de_cambio(self):
        r = self.client.post(
            f"/api/v1/platform/clinics/{self.tenant.id}/admin/reset-password/"
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.must_change_password)
        self.assertTrue(self.admin.check_password(r.data["temporary_password"]))
