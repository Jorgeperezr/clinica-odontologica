"""
Extracción de la paleta de colores del logotipo (Sprint 33).

Estrategia: reducir la imagen, cuantizar a pocos colores, descartar los
casi blancos/negros/grises (fondo y contornos) y elegir como color
primario el dominante con mayor peso, y como secundario el siguiente de
tono suficientemente distinto. El ajuste de contraste para accesibilidad
se hace en el frontend al derivar los tonos (el color primario se
oscurece hasta contrastar con texto blanco).
"""

import colorsys

from PIL import Image


def _rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _saturation_value(rgb):
    r, g, b = [v / 255 for v in rgb]
    h, lightness, s = colorsys.rgb_to_hls(r, g, b)
    return h, lightness, s


def extract_palette(fileobj):
    """
    Devuelve {"primary": "#...", "secondary": "#..."} a partir del logo.
    Si la imagen es monocroma o sin colores útiles, secondary puede
    repetir un tono derivado del primario.
    """
    img = Image.open(fileobj).convert("RGB")
    img.thumbnail((96, 96))
    # Cuantizar a 12 colores y contarlos
    quant = img.quantize(colors=12, method=Image.Quantize.FASTOCTREE)
    palette = quant.getpalette()
    counts = sorted(quant.getcolors(), reverse=True)  # [(count, index), ...]

    candidates = []
    for count, idx in counts:
        rgb = tuple(palette[idx * 3: idx * 3 + 3])
        h, lightness, s = _saturation_value(rgb)
        # Descartar fondos casi blancos, casi negros y grises sin saturación
        if lightness > 0.92 or lightness < 0.08 or s < 0.18:
            continue
        candidates.append((count, rgb, h))

    if not candidates:
        return {"primary": "", "secondary": ""}

    primary_rgb, primary_h = candidates[0][1], candidates[0][2]
    secondary_rgb = None
    for _, rgb, h in candidates[1:]:
        # Tono a más de ~40 grados del primario = color realmente distinto
        if min(abs(h - primary_h), 1 - abs(h - primary_h)) > 0.11:
            secondary_rgb = rgb
            break
    if secondary_rgb is None and len(candidates) > 1:
        secondary_rgb = candidates[1][1]

    return {
        "primary": _rgb_to_hex(primary_rgb),
        "secondary": _rgb_to_hex(secondary_rgb) if secondary_rgb else "",
    }
