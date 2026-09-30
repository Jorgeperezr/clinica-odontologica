"""
La plataforma se llama Clinube.

La marca de la plataforma y la de cada clínica son cosas distintas: la
primera sale en lo que ve el personal (correos del sistema, título de la
API, configuración de la plataforma); la segunda, en todo lo que recibe
el paciente. Aquí se fija la primera y que no se cuele en la segunda.
"""

import pathlib
import re

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from apps.common.document_style import _brand_of
from apps.common.models import PlatformConfiguration, Tenant
from apps.configuration.models import ClinicBranding
from apps.configuration.temas import PRESETS


class MarcaDeLaPlataforma(TestCase):
    def test_nombre_de_la_plataforma(self):
        self.assertEqual(settings.MARCA, "Clinube")
        self.assertEqual(PlatformConfiguration.get_solo().platform_name, "Clinube")

    def test_el_remitente_por_omision_lleva_la_marca(self):
        self.assertIn("Clinube", settings.DEFAULT_FROM_EMAIL)

    def test_la_clinica_conserva_su_propio_nombre(self):
        t = Tenant.objects.create(name="Sonrisa Feliz")
        self.assertEqual(str(t), "Sonrisa Feliz")


class ColoresDeLosDocumentos(TestCase):
    """Los PDF toman el color principal del tema de la clínica, sea cual sea."""

    def test_una_clinica_nueva_imprime_con_la_paleta_de_clinube(self):
        t = Tenant.objects.create(name="Recién creada")
        self.assertEqual(_brand_of(t)["primary"], "#0e7490")

    def test_un_tema_predefinido_llega_a_los_documentos(self):
        # Antes solo llegaban los colores puestos a mano: con un tema
        # predefinido el PDF salía con el color de reserva.
        t = Tenant.objects.create(name="En grises")
        ClinicBranding.objects.create(tenant=t, theme={"preset": "sin_color", "primary": "", "secondary": ""})
        self.assertEqual(_brand_of(t)["primary"], "#404040")

    def test_los_colores_a_mano_siguen_mandando(self):
        t = Tenant.objects.create(name="A medida")
        ClinicBranding.objects.create(tenant=t, theme={"preset": "custom", "primary": "#7B1E3C", "secondary": ""})
        self.assertEqual(_brand_of(t)["primary"], "#7b1e3c")


# ── El logotipo vive tres veces: que no se separen ─────────────────────
#
# Los trazados de «clinube» están en el panel (frontend/lib/marca.js), en
# la app (movil/lib/logo.dart) y, los de la «c», en el favicon
# (frontend/app/icon.svg). Retocar uno y olvidar los otros daría un
# logotipo distinto en el teléfono y en el navegador; esto lo pone rojo.

_RAIZ = pathlib.Path(__file__).resolve().parents[3]


def _numeros(texto):
    return [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", texto)]


def _del_panel():
    js = (_RAIZ / "frontend" / "lib" / "marca.js").read_text(encoding="utf-8")
    palabra = re.search(r"export const TRAZOS = \{(.*?)\n\};", js, re.S).group(1)
    icono = re.search(r"export const TRAZOS_ICONO = \{(.*?)\n\};", js, re.S).group(1)

    def campo(bloque, nombre):
        return re.search(rf'{nombre}: "([^"]+)"', bloque).group(1)

    def cifras(bloque, nombre):
        return _numeros(re.search(rf"{nombre}: [\[{{]([^\]}}]+)[\]}}]", bloque).group(1))

    return {
        "cli": campo(palabra, "cli"), "nube": campo(palabra, "nube"), "c": campo(icono, "c"),
        "punto": cifras(palabra, "punto"), "caja": cifras(palabra, "caja"),
        "punto_icono": cifras(icono, "punto"), "caja_icono": cifras(icono, "caja"),
    }


def _de_la_app():
    dart = (_RAIZ / "movil" / "lib" / "logo.dart").read_text(encoding="utf-8")

    def cadena(nombre):
        bloque = re.search(rf"const {nombre} =\s*((?:'[^']*'\s*)+);", dart).group(1)
        return "".join(re.findall(r"'([^']*)'", bloque))

    def lista(nombre):
        return _numeros(re.search(rf"const {nombre} = \[([^\]]+)\];", dart).group(1))

    return {
        "cli": cadena("_cli"), "nube": cadena("_nube"), "c": cadena("_c"),
        "punto": lista("_punto"), "caja": lista("_caja"),
        "punto_icono": lista("_puntoIcono"), "caja_icono": lista("_cajaIcono"),
    }


class ElLogotipoEsElMismoEnTodasPartes(SimpleTestCase):
    def test_panel_y_app_dibujan_los_mismos_trazados(self):
        panel, app = _del_panel(), _de_la_app()
        for clave in panel:
            self.assertEqual(panel[clave], app[clave],
                             f"«{clave}» del logotipo difiere entre marca.js y logo.dart")

    def test_el_favicon_es_la_c_del_panel(self):
        svg = (_RAIZ / "frontend" / "app" / "icon.svg").read_text(encoding="utf-8")
        self.assertIn(f'd="{_del_panel()["c"]}"', svg)

    def test_la_comprobacion_puede_fallar(self):
        """Una prueba que no puede fallar no prueba nada."""
        self.assertNotEqual(_del_panel()["cli"], _del_panel()["nube"])

    def test_la_app_arranca_con_la_paleta_de_clinube(self):
        # Antes del primer ingreso la app no sabe de qué clínica es y usa
        # su marca neutra: tiene que ser la misma paleta que da el servidor.
        dart = (_RAIZ / "movil" / "lib" / "api" / "modelos.dart").read_text(encoding="utf-8")
        neutra = re.search(r"static const neutra = Marca\((.*?)\);", dart, re.S).group(1)
        principal = re.search(r"colorPrincipal: 0xFF([0-9A-Fa-f]{6})", neutra).group(1)
        secundario = re.search(r"colorSecundario: 0xFF([0-9A-Fa-f]{6})", neutra).group(1)
        self.assertEqual((f"#{principal}".lower(), f"#{secundario}".lower()), PRESETS["default"])
