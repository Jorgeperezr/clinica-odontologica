"""
Guardar un secreto de un tercero en la base, cifrado.

Aquí acaban los tokens de WhatsApp de cada clínica. No es una
contraseña de usuario —esas se hashean y no se recuperan jamás—: es una
credencial que el sistema TIENE que poder usar para llamar a Meta, así
que hay que poder descifrarla. Lo que se evita cifrándola es que un
volcado de la base, una copia de seguridad extraviada o un `SELECT` mal
dado entreguen las credenciales de todas las clínicas en texto plano.

La clave sale de `DJANGO_SECRET_KEY`. Consecuencia que conviene saber
ANTES de que ocurra: **si se cambia la clave secreta, los secretos
guardados dejan de poder descifrarse** y cada clínica tendrá que volver
a pegar su token. No se pierde nada más, y es preferible a guardar la
clave de cifrado junto a lo cifrado, que es no cifrar nada.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

_PREFIJO = "v1:"


def _cifrador():
    # Fernet quiere 32 bytes en base64url. La clave secreta de Django es
    # texto libre, así que se pasa por SHA-256 para fijar el tamaño.
    material = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(material))


def cifrar(texto):
    """Devuelve el secreto cifrado, o cadena vacía si no había nada."""
    limpio = (texto or "").strip()
    if not limpio:
        return ""
    return _PREFIJO + _cifrador().encrypt(limpio.encode("utf-8")).decode("ascii")


def descifrar(guardado):
    """
    El secreto en claro, o cadena vacía si no se puede.

    No lanza a propósito: quien llama es el envío de un recordatorio, y
    un token que ya no descifra —porque cambió la clave secreta— tiene
    que traducirse en «esta clínica no tiene WhatsApp configurado», no
    en un 500 que tumbe la tarea de recordatorios de TODAS las clínicas.
    """
    texto = (guardado or "").strip()
    if not texto.startswith(_PREFIJO):
        return ""
    try:
        return _cifrador().decrypt(texto[len(_PREFIJO):].encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""


def pista(texto):
    """
    Los últimos cuatro caracteres, para que el panel pueda decir «…aB3x»
    y el administrador reconozca cuál puso sin que el token vuelva nunca
    al navegador.
    """
    limpio = (texto or "").strip()
    return f"…{limpio[-4:]}" if len(limpio) >= 4 else ""
