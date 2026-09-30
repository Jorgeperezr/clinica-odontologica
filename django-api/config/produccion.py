"""
Qué debe cumplir la configuración para arrancar en PRODUCCIÓN.

`settings.py` trae valores por omisión pensados para desarrollo —una
clave secreta que está en el repositorio, DEBUG a mano—, y
`.env.example` trae otros de ejemplo. Los dos son públicos. Si se
despliega sin cambiarlos, Django arranca igual y en silencio:

  · con la SECRET_KEY por omisión cualquiera puede FIRMAR tokens de
    acceso válidos (los JWT se firman con ella) y entrar como quien
    quiera, sin contraseña;
  · con DEBUG=True, cualquier error enseña a quien lo provoque el
    código, la configuración y parte de los datos.

`docker-compose.prod.yml` fija DJANGO_ENTORNO=produccion, y en ese caso
`settings.py` llama a `exigir()`: el contenedor no arranca y dice qué
falta, en vez de servir datos clínicos con una puerta abierta.
"""

from django.core.exceptions import ImproperlyConfigured

# Valores que aparecen en el repositorio (settings.py, .env.example,
# guiones de desarrollo). Cualquiera que lo lea los conoce.
PUBLICOS = {
    "dev-only-insecure-key-change-me",
    "dev-only-insecure-key-change-me-never-use-in-production",
    "change-me-in-every-environment",
    "dev-only-key-long-enough-for-hmac-validation-0123456789",
    "dev-only-shared-secret-change-me",
    "change-me-shared-secret",
    "change-me",
    "clinica",
}

GENERAR = 'python3 -c "import secrets; print(secrets.token_urlsafe(50))"'


# Marcadores de las plantillas (.env.example, .env.production.example):
# «CAMBIAR-password-fuerte» tiene longitud de sobra y sigue siendo público.
MARCADORES = ("cambiar", "change-me", "changeme", "dev-only")


def _debil(valor, largo):
    return (not valor or valor in PUBLICOS or len(valor) < largo
            or any(m in valor.lower() for m in MARCADORES))


def problemas(ajustes):
    """Lista de lo que impide arrancar en producción (vacía si nada)."""
    fallos = []
    if ajustes.get("DEBUG"):
        fallos.append("DJANGO_DEBUG está activado: en producción debe ser False.")
    if _debil(ajustes.get("SECRET_KEY", ""), 50):
        fallos.append("DJANGO_SECRET_KEY falta, es de ejemplo o tiene menos de 50 caracteres. "
                      f"Genera una con: {GENERAR}")
    if _debil(ajustes.get("INTERNAL_SERVICE_TOKEN", ""), 32):
        fallos.append("INTERNAL_SERVICE_TOKEN falta, es de ejemplo o tiene menos de 32 caracteres. "
                      f"Genera uno con: {GENERAR}")
    clave_bd = (ajustes.get("DATABASES") or {}).get("default", {}).get("PASSWORD", "")
    if _debil(clave_bd, 12):
        fallos.append("POSTGRES_PASSWORD falta, es de ejemplo o tiene menos de 12 caracteres.")
    return fallos


def exigir(ajustes):
    fallos = problemas(ajustes)
    if fallos:
        raise ImproperlyConfigured(
            "La configuración de producción no es segura; el servidor no arranca así:\n  - "
            + "\n  - ".join(fallos)
            + "\nSe corrige en el archivo .env del servidor (ver DEPLOY.md)."
        )
