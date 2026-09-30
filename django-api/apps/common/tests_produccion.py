"""
Producción no arranca con la configuración de ejemplo (config/produccion.py).

Lo que se fija: que los valores que están en el repositorio —y que por
tanto conoce cualquiera— no sirvan en producción, y que el error diga
qué corregir en vez de un traceback.
"""

import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

from config.produccion import problemas

BUENA = "k" * 20 + "Zq8-" * 10
BD_BUENA = {"default": {"PASSWORD": "una-clave-de-base-larga"}}


def ajustes(**cambios):
    base = {"DEBUG": False, "SECRET_KEY": BUENA, "INTERNAL_SERVICE_TOKEN": BUENA, "DATABASES": BD_BUENA}
    base.update(cambios)
    return base


class ReglasDeProduccion(SimpleTestCase):
    def test_una_configuracion_propia_arranca(self):
        self.assertEqual(problemas(ajustes()), [])

    def test_debug_no(self):
        [fallo] = problemas(ajustes(DEBUG=True))
        self.assertIn("DJANGO_DEBUG", fallo)

    def test_claves_publicas_o_cortas_no(self):
        from django.conf import settings

        for clave in ("change-me-in-every-environment", settings.SECRET_KEY, "", "corta",
                      "dev-only-cualquier-cosa-" + "x" * 60):
            with self.subTest(clave=clave):
                [fallo] = problemas(ajustes(SECRET_KEY=clave))
                self.assertIn("DJANGO_SECRET_KEY", fallo)
                self.assertIn("secrets.token_urlsafe", fallo)

    def test_token_interno_y_base_de_datos(self):
        fallos = problemas(ajustes(INTERNAL_SERVICE_TOKEN="change-me-shared-secret",
                                   DATABASES={"default": {"PASSWORD": "change-me"}}))
        self.assertEqual(len(fallos), 2)

    def test_los_marcadores_de_las_plantillas_no_valen_aunque_sean_largos(self):
        """Los de .env.production.example, tal cual: tienen longitud de sobra."""
        from pathlib import Path

        plantilla = Path(__file__).resolve().parents[3] / ".env.production.example"
        valores = dict(linea.split("=", 1) for linea in plantilla.read_text().splitlines()
                       if "=" in linea and not linea.startswith("#"))
        fallos = problemas(ajustes(
            SECRET_KEY=valores["DJANGO_SECRET_KEY"],
            INTERNAL_SERVICE_TOKEN=valores["INTERNAL_SERVICE_TOKEN"],
            DATABASES={"default": {"PASSWORD": valores["POSTGRES_PASSWORD"]}},
        ))
        self.assertEqual(len(fallos), 3, fallos)

    def test_se_listan_todos_a_la_vez(self):
        """Arreglar de uno en uno, arrancando cada vez, es desesperante."""
        self.assertEqual(len(problemas({"DEBUG": True})), 4)


class ArranqueReal(SimpleTestCase):
    """El mismo `settings.py` que carga gunicorn, en un proceso aparte."""

    def cargar(self, **entorno):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("DJANGO_", "POSTGRES_", "INTERNAL_"))}
        env.update(entorno, DJANGO_SETTINGS_MODULE="config.settings")
        return subprocess.run([sys.executable, "-c", "import django; django.setup()"],
                              cwd=Path(__file__).resolve().parents[2], env=env,
                              capture_output=True, text=True, timeout=60)

    def test_con_valores_de_ejemplo_no_arranca_y_dice_por_que(self):
        r = self.cargar(DJANGO_ENTORNO="produccion", DJANGO_DEBUG="True",
                        DJANGO_SECRET_KEY="change-me-in-every-environment")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("ImproperlyConfigured", r.stderr)
        self.assertIn("DJANGO_SECRET_KEY", r.stderr)

    def test_con_valores_propios_arranca(self):
        r = self.cargar(DJANGO_ENTORNO="produccion", DJANGO_DEBUG="False", DJANGO_SECRET_KEY=BUENA,
                        INTERNAL_SERVICE_TOKEN=BUENA, POSTGRES_PASSWORD="una-clave-de-base-larga")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_en_desarrollo_no_se_exige(self):
        self.assertEqual(self.cargar().returncode, 0)


class EsquemaDeLaApi(SimpleTestCase):
    """Sin DEBUG, el mapa de la API no se enseña a quien no ha entrado."""

    def test_sin_sesion_no_hay_esquema(self):
        from django.test import Client

        from config import settings as ajustes

        self.assertFalse(ajustes.DEBUG)
        self.assertEqual(ajustes.SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"],
                         ["rest_framework.permissions.IsAuthenticated"])
        self.assertEqual(Client().get("/api/v1/schema/").status_code, 401)
