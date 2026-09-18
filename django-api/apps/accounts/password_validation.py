"""
Contraseñas comunes EN ESPAÑOL.

`CommonPasswordValidator` de Django trae una lista de veinte mil
contraseñas filtradas de brechas reales, y funciona muy bien... en
inglés. Este sistema lo usan clínicas ecuatorianas, y ahí la lista no
cubre casi nada: comprobado en el navegador, `contrasena12` la pasa
entera y entra sin una sola queja.

Importa justo aquí y no en abstracto. La pantalla de primer ingreso le
dice al administrador de la clínica que su contraseña «no puede ser una
contraseña común», y esa promesa era falsa para exactamente las
contraseñas que iba a escribir una persona que trabaja en español. Y es
el peor sitio donde puede ser falsa: es la contraseña que estrena la
cuenta con acceso a todos los datos clínicos.

La lista es corta a propósito. No pretende sustituir a la de Django
—que se sigue aplicando, las dos se acumulan— sino tapar lo que a
aquella se le escapa por el idioma: palabras castellanas de teclado,
nombres del oficio y el nombre del propio sistema.
"""

import re
import unicodedata

from django.core.exceptions import ValidationError

# Se guardan SIN tildes, sin mayúsculas y sin los dígitos del final,
# porque así es como se normaliza lo que escribe el usuario antes de
# buscarlo: `Clínica2026` y `clinica` son la misma contraseña con un
# disfraz que no cuesta nada quitar.
COMUNES_EN_ESPANOL = {
    # Teclado y palabras de andar por casa
    "contrasena", "contraseña", "clave", "claveacceso", "miclave",
    "secreto", "password", "passwordes", "qwerty", "asdfgh", "zxcvbn",
    "bienvenido", "bienvenida", "iniciar", "ingreso", "acceso", "entrar",
    "usuario", "administrador", "admin", "adminadmin", "administracion",
    "sistema", "seguridad", "prueba", "pruebas", "temporal", "cambiar",
    "hola", "holahola", "holamundo", "tequiero", "amor", "familia",
    "estrella", "mariposa", "principal", "personal", "trabajo", "oficina",
    # El oficio: lo primero que se escribe cuando hay que inventar algo
    "clinica", "clinicaodontologica", "odontologia", "odontologica",
    "odontologo", "odontologa", "dentista", "dental", "consultorio",
    "diente", "dientes", "muela", "muelas", "sonrisa", "paciente",
    "pacientes", "doctor", "doctora", "doctorito", "salud", "medico",
    "recepcion", "secretaria", "asistente", "auxiliar",
    # Geografía y fechas locales, que salen solas
    "ecuador", "quito", "guayaquil", "cuenca", "ambato", "loja",
    "manabi", "pichincha", "azuay", "esmeraldas",
}

_SOLO_LETRAS_Y_NUMEROS = re.compile(r"[^a-z0-9ñ]+")
_DIGITOS_AL_FINAL = re.compile(r"\d+$")


def normalizar(contrasena):
    """
    Deja la contraseña como se guarda en la lista.

    Quita tildes, pasa a minúsculas, tira los separadores y suelta los
    dígitos del final. Ese último paso es el que hace el trabajo: casi
    nadie escribe `clinica` a secas, escribe `Clinica2026` o
    `clinica.123`, que es la misma idea con un año detrás.
    """
    sin_tildes = "".join(
        letra for letra in unicodedata.normalize("NFD", contrasena or "")
        # La eñe se conserva: `unicodedata` la parte en n + tilde y sin
        # este cuidado `contraseña` se volvería `contrasena`, que ya
        # está en la lista, pero `ñoño` se volvería `nono`, que no es la
        # misma palabra.
        if unicodedata.category(letra) != "Mn" or letra == "̃"
    )
    sin_tildes = unicodedata.normalize("NFC", sin_tildes).lower()
    limpia = _SOLO_LETRAS_Y_NUMEROS.sub("", sin_tildes)
    return _DIGITOS_AL_FINAL.sub("", limpia) or limpia


class ContrasenaComunEnEspanolValidator:
    """Se suma a los validadores de Django; no sustituye a ninguno."""

    def validate(self, password, user=None):
        if normalizar(password) in COMUNES_EN_ESPANOL:
            raise ValidationError(
                "Esta contraseña es demasiado fácil de adivinar: es una "
                "palabra común o del ámbito de la clínica. Combina varias "
                "palabras que solo tengan sentido para usted.",
                code="password_too_common_es",
            )

    def get_help_text(self):
        return (
            "No puede ser una palabra común en español ni del ámbito "
            "odontológico, aunque lleve números detrás."
        )
