"""
Ningún fallo se traga sin decir por qué (Sprint 86).

Tragarse una excepción es a veces lo correcto: un fallo del almacén no
puede deshacer un tratamiento que ya se hizo, ni un logotipo ilegible
impedir que salga una receta. Lo que nunca es correcto es tragárselo
**sin dejar constancia de la decisión**, porque entonces nadie sabe si
fue deliberado o un descuido, y el día que ese fallo importe no habrá ni
una línea que lo cuente.

La regla es sencilla y se comprueba aquí: un `except … : pass` lleva
encima un comentario que explica por qué ese fallo puede ignorarse. Si
no puede ignorarse, no es un `pass`: es un `logger.warning`.

Se comprueba con una prueba y no con un linter porque la regla es del
proyecto, no del lenguaje, y así viaja con el código en el mismo sitio
donde se lee todo lo demás.
"""

import pathlib
import re

from django.test import SimpleTestCase

RAIZ = pathlib.Path(__file__).resolve().parent.parent

# `except ...:` seguido de comentarios opcionales y luego `pass`.
SILENCIO = re.compile(r"except[^\n]*:\s*\n((?:[ \t]*#[^\n]*\n)*)[ \t]*pass\b")


class CadaSilencioLlevaSuMotivoTests(SimpleTestCase):
    def test_ningun_except_pass_sin_explicacion(self):
        sin_motivo = []
        for archivo in sorted(RAIZ.rglob("*.py")):
            if "migrations" in archivo.parts or archivo.name.startswith("tests"):
                continue
            texto = archivo.read_text(encoding="utf-8")
            for encaje in SILENCIO.finditer(texto):
                if encaje.group(1).strip():
                    continue
                linea = texto[: encaje.start()].count("\n") + 1
                sin_motivo.append(f"{archivo.relative_to(RAIZ)}:{linea}")

        self.assertEqual(
            sin_motivo, [],
            "Estos sitios se tragan un fallo sin decir por qué:\n  "
            + "\n  ".join(sin_motivo)
            + "\n\nEscribe encima del `pass` por qué ese fallo se puede "
              "ignorar. Si no se puede, usa logger.warning(..., exc_info=True).",
        )

    def test_la_comprobacion_puede_fallar(self):
        """
        Una prueba que no puede fallar no prueba nada: se le da un trozo
        de código con un silencio sin justificar y tiene que detectarlo.
        """
        malo = "try:\n    algo()\nexcept Exception:\n    pass\n"
        bueno = "try:\n    algo()\nexcept Exception:\n    # da igual: hay reserva\n    pass\n"
        self.assertTrue(SILENCIO.search(malo))
        self.assertEqual(SILENCIO.search(malo).group(1).strip(), "")
        self.assertTrue(SILENCIO.search(bueno).group(1).strip())
