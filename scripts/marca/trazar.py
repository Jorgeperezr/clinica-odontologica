"""
Convierte «clinube» en los trazados del logotipo.

Salen de DM Sans Bold (tamaño óptico 40, licencia SIL OFL) compuesta con
HarfBuzz —el mismo interletraje que aplica el navegador— y con un
espaciado de −0,035 em. Imprime un JSON con los trazados de «cli»,
«nube», el punto de la i y la «c» del icono, en unidades de la fuente
(1000 por em) y con la y hacia abajo, como los usa SVG.

NO es parte del proyecto: fontTools y uharfbuzz no están en ningún
requirements. Solo hace falta para volver a dibujar el logotipo; ver
README.md en esta carpeta.

    python trazar.py DMSans-Bold-opsz40.ttf > logo.json
"""

import json
import sys

import uharfbuzz as hb
from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

TRACKING = -35                # letter-spacing −0,035 em, el del diseño aprobado
PUNTO_R, PUNTO_CY = 90, 628   # punto de la i: arriba, a la altura del de la «i»
ICONO_R, ICONO_CY = 112, 612  # en el icono, algo mayor: a 16 px el otro se pierde


def _r(v):
    v = round(v, 1)
    return str(int(v)) if v == int(v) else str(v)


class Pluma(BasePen):
    """Solo M, L, Q y Z absolutos: lo que saben leer marca.js y logo.dart."""

    def __init__(self, glifos, dx):
        super().__init__(glifos)
        self.dx, self.d = dx, []

    def _p(self, pt):
        return f"{_r(pt[0] + self.dx)} {_r(-pt[1])}"

    def _moveTo(self, pt):
        self.d.append("M" + self._p(pt))

    def _lineTo(self, pt):
        self.d.append("L" + self._p(pt))

    def _qCurveToOne(self, a, b):
        self.d.append("Q" + self._p(a) + " " + self._p(b))

    def _curveToOne(self, a, b, c):
        raise ValueError("curva cúbica inesperada en una fuente TrueType")

    def _closePath(self):
        self.d.append("Z")

    _endPath = _closePath


def trazar(ruta):
    fuente = TTFont(ruta)
    glifos = fuente.getGlyphSet()
    hbf = hb.Font(hb.Face(hb.Blob.from_file_path(ruta)))
    buf = hb.Buffer()
    buf.add_str("clınube")          # con ı sin punto: el punto es nuestro
    buf.guess_segment_properties()
    hb.shape(hbf, buf, {"kern": True})

    x, trozos, x_i, x_e = 0, [], None, 0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        nombre = fuente.getGlyphName(info.codepoint)
        pluma = Pluma(glifos, x + pos.x_offset)
        glifos[nombre].draw(pluma)
        trozos.append("".join(pluma.d))
        if nombre == "dotlessi":
            x_i = x
        x_e = x
        x += pos.x_advance + TRACKING

    # Bordes reales: izquierda de la «c», derecha de la «e».
    def caja_de(glifo):
        b = BoundsPen(glifos)
        glifos[glifo].draw(b)
        return b.bounds
    c0 = caja_de("c")
    e1 = caja_de("e")[2] + x_e
    i0, _, i1, _ = caja_de("dotlessi")

    pc = Pluma(glifos, 0)
    glifos["c"].draw(pc)
    icono_cx = c0[2] + 6 + ICONO_R
    return {
        "cli": "".join(trozos[:3]),
        "nube": "".join(trozos[3:]),
        "punto": {"cx": round(x_i + (i0 + i1) / 2, 1), "cy": -PUNTO_CY, "r": PUNTO_R},
        "caja": [c0[0], -(PUNTO_CY + PUNTO_R), round(e1 - c0[0], 1), PUNTO_CY + PUNTO_R - c0[1]],
        "icono": {
            "c": "".join(pc.d),
            "punto": {"cx": icono_cx, "cy": -ICONO_CY, "r": ICONO_R},
            "caja": [c0[0], -(ICONO_CY + ICONO_R), icono_cx + ICONO_R - c0[0], ICONO_CY + ICONO_R - c0[1]],
        },
    }


if __name__ == "__main__":
    json.dump(trazar(sys.argv[1]), sys.stdout, indent=1)
