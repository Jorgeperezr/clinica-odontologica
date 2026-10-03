"""
Que la promesa de la pantalla de primer ingreso sea cierta en español.

Salió de recorrer el alta de una clínica en el navegador: la cuenta
recién entregada eligió `contrasena12` y el sistema la aceptó sin una
queja, porque la lista de contraseñas comunes de Django está en inglés.
"""

from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.accounts.password_validation import normalizar
from apps.common.models import Tenant


class NormalizarTests(SimpleTestCase):
    def test_quita_tildes_mayusculas_y_separadores(self):
        self.assertEqual(normalizar("Clínica"), "clinica")
        self.assertEqual(normalizar("CLINICA"), "clinica")
        self.assertEqual(normalizar("cli-ni.ca"), "clinica")

    def test_suelta_los_digitos_del_final(self):
        """Casi nadie escribe «clinica»; escribe «Clinica2026»."""
        self.assertEqual(normalizar("Clinica2026"), "clinica")
        self.assertEqual(normalizar("contrasena12"), "contrasena")

    def test_conserva_la_ene(self):
        """
        Sin este cuidado la eñe se descompone y `ñoño` acabaría siendo
        `nono`, que no es la misma palabra.
        """
        self.assertEqual(normalizar("Ñoño"), "ñoño")
        self.assertEqual(normalizar("contraseña"), "contraseña")

    def test_una_contrasena_solo_de_digitos_no_se_queda_vacia(self):
        self.assertEqual(normalizar("12345678"), "12345678")


class ContrasenasComunesEnEspanolTests(SimpleTestCase):
    def test_las_que_django_dejaba_pasar(self):
        for clave in ("contrasena12", "Clinica2026", "odontologia1",
                      "administrador", "Guayaquil2026", "miclave123",
                      "dentista2026", "bienvenido1"):
            with self.subTest(clave=clave):
                with self.assertRaises(ValidationError, msg=f"«{clave}» fue aceptada"):
                    validate_password(clave)

    def test_una_contrasena_de_verdad_sigue_valiendo(self):
        for clave in ("mi-clave-elegida-9animales", "otra-distinta-7tigres",
                      "la-que-eligio-la-clinica-7", "cuatro-palabras-sin-relacion"):
            with self.subTest(clave=clave):
                validate_password(clave)   # no debe lanzar

    def test_no_se_pierden_los_validadores_de_django(self):
        """El nuevo se SUMA; los de siempre siguen aplicándose."""
        with self.assertRaises(ValidationError):
            validate_password("corta")            # demasiado corta
        with self.assertRaises(ValidationError):
            validate_password("1234567890123")    # solo dígitos


class AlElegirLaSuyaTampocoValeUnaComunTests(APITestCase):
    """Lo mismo, pero por donde pasa de verdad: el cambio obligatorio."""

    def setUp(self):
        # Cada `entrar()` es una petición ANÓNIMA y el cupo de anónimo
        # (20/min por IP) vive en la caché y sobrevive entre pruebas.
        # Sin esto, esta clase deja el cupo gastado para lo que corra
        # después, y el 429 aparece en OTRO archivo.
        cache.clear()
        tenant = Tenant.objects.create(name="Clínica Español", ruc="1790000092040")
        self.admin = User.objects.create_user(
            email="admin@espanol.ec", password="temporal-de-fabrica-123",
            role="admin", tenant=tenant,
        )
        self.admin.must_change_password = True
        self.admin.save(update_fields=["must_change_password"])
        r = self.client.post("/api/v1/auth/login/",
                             {"email": "admin@espanol.ec", "password": "temporal-de-fabrica-123"},
                             format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")

    def test_contrasena12_ya_no_entra(self):
        r = self.client.post("/api/v1/auth/change-password/",
                             {"new_password": "contrasena12"}, format="json")
        self.assertEqual(r.status_code, 400, "aceptó «contrasena12»")
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.must_change_password, "la desbloqueó igualmente")

    def test_y_el_aviso_explica_qué_hacer(self):
        r = self.client.post("/api/v1/auth/change-password/",
                             {"new_password": "Clinica2026"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Combina varias palabras", str(r.data))
