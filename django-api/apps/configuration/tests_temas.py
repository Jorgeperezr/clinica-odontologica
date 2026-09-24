"""
Que el panel y la app pinten la MISMA clínica del mismo color.

La tabla de temas vive dos veces —en Python, para resolverla en el
servidor, y en `frontend/lib/theme.js`, que el panel usa para pintarse a
sí mismo—. Dos copias se separan solas: alguien añade un tema, lo pone
en una y se olvida de la otra, y a partir de ahí la misma clínica se ve
azul en el panel y verde en el teléfono.

Esta prueba lee el JavaScript de verdad y compara. Es fea a propósito:
más fea es descubrirlo comparando dos pantallas.
"""

import pathlib
import re

from django.test import SimpleTestCase

from apps.configuration.temas import PRESETS, resolver

JS = (pathlib.Path(__file__).resolve().parents[3]
      / "frontend" / "lib" / "theme.js")


def _presets_del_panel():
    texto = JS.read_text(encoding="utf-8")
    bloque = re.search(r"export const PRESETS = \[(.*?)\];", texto, re.S)
    if not bloque:
        return None
    encontrados = {}
    for linea in re.finditer(
        r'key:\s*"([^"]+)".*?primary:\s*"(#[0-9a-fA-F]{6})".*?'
        r'secondary:\s*"(#[0-9a-fA-F]{6})"',
        bloque.group(1),
    ):
        clave, principal, secundario = linea.groups()
        encontrados[clave] = (principal.lower(), secundario.lower())
    return encontrados


class LasDosTablasCoincidenTests(SimpleTestCase):
    def test_el_panel_y_el_servidor_tienen_los_mismos_temas(self):
        del_panel = _presets_del_panel()
        self.assertIsNotNone(
            del_panel, f"No pude leer PRESETS de {JS}. ¿Cambió el formato?")
        self.assertEqual(
            {k: (a.lower(), b.lower()) for k, (a, b) in PRESETS.items()},
            del_panel,
            "La tabla de temas de apps/configuration/temas.py y la de "
            "frontend/lib/theme.js se han separado. La misma clínica se "
            "vería de un color en el panel y de otro en la app.",
        )

    def test_la_comprobacion_puede_fallar(self):
        """Una prueba que no puede fallar no prueba nada."""
        self.assertNotEqual(_presets_del_panel(), {"inventado": ("#000000", "#ffffff")})


class ResolverTests(SimpleTestCase):
    def test_un_preset_conocido(self):
        self.assertEqual(resolver({"preset": "petroleo"}), ("#0e5c63", "#9fe1cb"))

    def test_sin_tema_se_cae_al_del_sistema(self):
        self.assertEqual(resolver(None), PRESETS["default"])
        self.assertEqual(resolver({}), PRESETS["default"])

    def test_auto_usa_los_colores_guardados(self):
        # «auto» son los colores sacados del logotipo: no hay preset que
        # buscar, los buenos son los que están guardados.
        self.assertEqual(
            resolver({"preset": "auto", "primary": "#AB12CD", "secondary": "#123456"}),
            ("#ab12cd", "#123456"),
        )

    def test_un_color_con_mala_pinta_no_llega_a_la_app(self):
        # Un color inválido pintaría la app de negro o la haría reventar
        # al parsearlo; se cae al del sistema, que siempre es legible.
        self.assertEqual(
            resolver({"preset": "custom", "primary": "rojo", "secondary": "#zzz"}),
            PRESETS["default"],
        )
