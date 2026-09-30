"""
Genera los iconos de la app —Android, iOS y web— desde el logotipo.

Lee los trazados de la «c» y su punto de `frontend/lib/marca.js`, que es
de donde los toma todo lo demás, y los dibuja con Pillow (ya está en
`django-api/requirements.txt`: no hace falta nada nuevo).

    .venv/bin/python scripts/marca/iconos.py

Sobrescribe los PNG de `movil/android/.../mipmap-*`, del AppIcon de iOS
y de `movil/web/`. El fondo del icono adaptativo de Android es el color
`ic_launcher_background` de `res/values/colors.xml`.
"""

import pathlib
import re

from PIL import Image, ImageDraw

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MOVIL = RAIZ / "movil"
TINTA, BLANCO, CIAN_LUZ = (11, 18, 32), (255, 255, 255), (103, 232, 249)
SOBREMUESTREO = 4


def _icono_de_marca_js():
    js = (RAIZ / "frontend" / "lib" / "marca.js").read_text(encoding="utf-8")
    bloque = re.search(r"export const TRAZOS_ICONO = \{(.*?)\n\};", js, re.S).group(1)
    numeros = lambda t: [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", t)]  # noqa: E731
    return {
        "c": re.search(r'c: "([^"]+)"', bloque).group(1),
        "punto": numeros(re.search(r"punto: \{([^}]+)\}", bloque).group(1)),
        "caja": numeros(re.search(r"caja: \[([^\]]+)\]", bloque).group(1)),
    }


def _poligonos(d, pasos=24):
    """M, L, Q y Z a polígonos: cada curva, en `pasos` tramos rectos."""
    fichas = re.findall(r"[MLQZ]|-?\d+(?:\.\d+)?", d)
    i, polis, actual, pos = 0, [], [], (0.0, 0.0)

    def n():
        nonlocal i
        i += 1
        return float(fichas[i - 1])

    while i < len(fichas):
        orden = fichas[i]
        i += 1
        if orden == "M":
            if actual:
                polis.append(actual)
            pos = (n(), n())
            actual = [pos]
        elif orden == "L":
            pos = (n(), n())
            actual.append(pos)
        elif orden == "Q":
            c, p = (n(), n()), (n(), n())
            for k in range(1, pasos + 1):
                t = k / pasos
                actual.append(((1 - t) ** 2 * pos[0] + 2 * (1 - t) * t * c[0] + t * t * p[0],
                               (1 - t) ** 2 * pos[1] + 2 * (1 - t) * t * c[1] + t * t * p[1]))
            pos = p
        elif orden == "Z":
            polis.append(actual)
            actual = []
    if actual:
        polis.append(actual)
    return polis


ICONO = _icono_de_marca_js()
C = _poligonos(ICONO["c"])


def dibujar(tam, fondo, alto_rel, esquina=0.0, lleno=1.0, alfa=True):
    """
    fondo=None deja el lienzo transparente (primer plano de Android).
    alto_rel: alto del dibujo respecto al lienzo. lleno: parte del lienzo
    que ocupa el cuadrado de fondo (el icono de siempre de Android lleva
    un margen transparente).
    """
    s = tam * SOBREMUESTREO
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    lapiz = ImageDraw.Draw(im)
    if fondo:
        m = s * (1 - lleno) / 2
        lapiz.rounded_rectangle([m, m, s - m, s - m], radius=s * esquina * lleno, fill=fondo + (255,))
    x0, y0, w, h = ICONO["caja"]
    esc = s * alto_rel / h
    ox = (s - w * esc) / 2 + s * 0.012 - x0 * esc   # la «c» pesa a la izquierda
    oy = (s - h * esc) / 2 - y0 * esc
    for pol in C:
        lapiz.polygon([(ox + x * esc, oy + y * esc) for x, y in pol], fill=BLANCO + (255,))
    cx, cy, r = ICONO["punto"]
    cx, cy, r = ox + cx * esc, oy + cy * esc, r * esc
    lapiz.ellipse([cx - r, cy - r, cx + r, cy + r], fill=CIAN_LUZ + (255,))
    im = im.resize((tam, tam), Image.LANCZOS)
    if not alfa:
        plano = Image.new("RGB", (tam, tam), fondo)
        plano.paste(im, mask=im.split()[3])
        im = plano
    return im


def guardar(im, ruta):
    ruta = MOVIL / ruta
    ruta.parent.mkdir(parents=True, exist_ok=True)
    im.save(ruta, optimize=True)


if __name__ == "__main__":
    # Android: el de siempre (hasta Android 7) y el adaptativo (8 en adelante).
    for carpeta, px in (("mdpi", 48), ("hdpi", 72), ("xhdpi", 96), ("xxhdpi", 144), ("xxxhdpi", 192)):
        res = f"android/app/src/main/res/mipmap-{carpeta}"
        guardar(dibujar(px, TINTA, 0.50, esquina=0.22, lleno=0.92), f"{res}/ic_launcher.png")
        guardar(dibujar(round(px * 108 / 48), None, 0.37), f"{res}/ic_launcher_foreground.png")

    # iOS: a sangre y sin transparencia (la App Store rechaza el alfa).
    ios = "ios/Runner/Assets.xcassets/AppIcon.appiconset"
    for archivo in sorted((MOVIL / ios).glob("Icon-App-*.png")):
        m = re.match(r"Icon-App-([\d.]+)x[\d.]+@(\d)x\.png", archivo.name)
        if m:
            guardar(dibujar(round(float(m.group(1)) * int(m.group(2))), TINTA, 0.52, alfa=False),
                    f"{ios}/{archivo.name}")

    # Web: normales, «maskable» (el dibujo dentro de la zona segura) y favicon.
    for px in (192, 512):
        guardar(dibujar(px, TINTA, 0.52, esquina=0.24), f"web/icons/Icon-{px}.png")
        guardar(dibujar(px, TINTA, 0.42), f"web/icons/Icon-maskable-{px}.png")
    guardar(dibujar(32, TINTA, 0.58, esquina=0.24), "web/favicon.png")
    print("Iconos de la app regenerados.")
