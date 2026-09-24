"""
Los temas predefinidos, resueltos a colores concretos.

Existe para que **quien resuelve el tema sea el servidor**. La
alternativa —que cada cliente lleve su propia tabla de presets— tiene un
final conocido: el panel y la app enseñan colores distintos para la
misma clínica en cuanto alguien añade un tema y se olvida de uno de los
dos. Es el mismo motivo por el que los estados de las citas se mandan ya
traducidos y la app no guarda su tabla.

**Esta tabla y la de `frontend/lib/theme.js` tienen que coincidir.** Hay
una prueba que lo comprueba leyendo el archivo JavaScript, así que
cambiar uno sin el otro se pone rojo en vez de descubrirse mirando dos
pantallas una al lado de la otra.
"""

# Mismo orden y mismas claves que PRESETS en frontend/lib/theme.js.
PRESETS = {
    "default": ("#14639e", "#bcdcf2"),
    "oceano": ("#0f4c81", "#a7d3f0"),
    "petroleo": ("#0e5c63", "#9fe1cb"),
    "bosque": ("#1d6b3c", "#b6e2c5"),
    "vino": ("#7b1e3c", "#f0c9d4"),
    "grafito": ("#374151", "#c7d2de"),
    "arena": ("#8a5a2b", "#ecd9bd"),
}

POR_DEFECTO = PRESETS["default"]


def resolver(theme):
    """
    Devuelve (principal, secundario) en #rrggbb.

    Un `preset` desconocido no es un error: puede ser «auto» —los
    colores que se sacaron del logotipo— o «custom», y en los dos casos
    los colores buenos son los que están guardados. Solo si tampoco hay
    guardados se cae al tema del sistema.
    """
    if not isinstance(theme, dict):
        return POR_DEFECTO
    preset = str(theme.get("preset") or "default")
    if preset in PRESETS:
        return PRESETS[preset]
    principal = _hex(theme.get("primary")) or POR_DEFECTO[0]
    secundario = _hex(theme.get("secondary")) or POR_DEFECTO[1]
    return (principal, secundario)


def _hex(valor):
    """Solo se acepta #rrggbb: lo que venga raro se descarta."""
    texto = str(valor or "").strip()
    if len(texto) != 7 or not texto.startswith("#"):
        return ""
    try:
        int(texto[1:], 16)
    except ValueError:
        return ""
    return texto.lower()
