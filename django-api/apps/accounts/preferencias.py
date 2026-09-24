"""
Preferencias de cada profesional.

A diferencia de las funcionalidades (`apps/common/funcionalidades.py`),
que decide el dueño de la plataforma para TODA una clínica, esto lo
decide cada persona para sí misma. Las dos cosas se combinan: una
preferencia solo tiene efecto si la clínica tiene contratada la
funcionalidad de la que depende. Un doctor no puede encenderse el
odontograma 3D si su clínica no lo tiene; sí puede apagárselo aunque la
clínica lo tenga, porque trabaja más cómodo con el clásico o porque su
equipo lo mueve con dificultad.

Igual que con las funcionalidades, las claves desconocidas se descartan
y las que faltan toman su valor por defecto, así que añadir una
preferencia nueva no necesita migración de datos.
"""

CATALOGO = {
    "odontograma_3d": {
        "etiqueta": "Odontograma 3D",
        "por_defecto": True,
        # Solo tiene efecto si la clínica tiene contratada esta funcionalidad.
        "funcionalidad": "odontograma_3d",
    },
}

POR_DEFECTO = {clave: d["por_defecto"] for clave, d in CATALOGO.items()}


def normalizar(valores):
    """Lo guardado, completado con los valores por defecto y sin claves ajenas."""
    valores = valores if isinstance(valores, dict) else {}
    return {clave: bool(valores.get(clave, defecto)) for clave, defecto in POR_DEFECTO.items()}
