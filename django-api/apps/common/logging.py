"""
Registro estructurado y correlación de peticiones (Sprint 75).

## Por qué

El proyecto no tenía bloque `LOGGING`, y eso no significaba «registro por
defecto»: significaba **silencio**. Comprobado con un 500 real y
`DEBUG=False`: el cliente recibe su 500 y la traza no aparece por ningún
lado. El único logger que trae Django por defecto es `django`, con los
manejadores `console` —filtrado por `require_debug_true`, así que callado
en producción— y `mail_admins`, que necesita `ADMINS` y un backend de
correo; `ADMINS` está vacío. Resultado: cuando el panel de la clínica
falla, nadie llega a enterarse de por qué.

## Qué se registra, y qué NO

Esto es un sistema de datos de salud. Un registro es un archivo más, se
copia a un agregador, se conserva meses y lo lee gente que no tiene por
qué ver la historia de nadie. Así que aquí la regla no es «registrar
mucho» sino **registrar lo justo para diagnosticar sin identificar**:

  SÍ  método, ruta, estado, duración, id de correlación, id de usuario,
      id de clínica, nombre de la excepción y traza.
  NO  nombres, cédulas, teléfonos, correos, contraseñas, tokens, ni el
      contenido de notas clínicas.

Dos decisiones que no son obvias:

1. **La cadena de consulta se recorta.** `/api/v1/patients/?search=Pérez`
   lleva el apellido de un paciente en la URL. Registrar la ruta completa
   metería nombres en el registro por la puerta de atrás. Se guarda la
   ruta y solo los NOMBRES de los parámetros, nunca sus valores.

2. **Los identificadores sí se registran.** El UUID de un paciente en la
   ruta es un seudónimo: sin la base de datos no dice quién es, y sin él
   no se puede reconstruir qué pasó. Es el equilibrio habitual, y conviene
   que quede escrito para que nadie lo «arregle» más adelante.

## Correlación

Cada petición recibe un identificador que viaja en un `ContextVar` —no en
un atributo del objeto `request`— para que lo vean también las funciones
que registran lejos de la vista, sin tener que pasarlo de mano en mano.
Va además en la cabecera `X-Request-ID` de la respuesta, de modo que un
usuario puede dar ese código al soporte y se encuentra su incidencia sin
buscar por hora y a ojo.
"""

import json
import logging
import re
import uuid
from contextvars import ContextVar

# Identificador de la petición en curso. Vacío fuera de una petición
# (tareas de Celery, comandos de gestión, el intérprete).
_request_id: ContextVar[str] = ContextVar("request_id", default="")


def set_request_id(value=None):
    """Fija el id de la petición en curso y lo devuelve."""
    nuevo = value or uuid.uuid4().hex[:16]
    _request_id.set(nuevo)
    return nuevo


def get_request_id():
    return _request_id.get()


def reset_request_id():
    _request_id.set("")


# Claves que nunca deben aparecer con su valor. Se comparan en minúsculas
# y por coincidencia parcial: `password`, `new_password` y `passphrase`
# entran todas por «passw».
CLAVES_SENSIBLES = (
    "passw", "token", "secret", "authorization", "cookie", "csrf",
    "national_id", "cedula", "phone", "telefono", "email", "correo",
    "first_name", "last_name", "full_name", "nombre", "apellido",
    # `request` merece estar aquí por un motivo concreto y comprobado: el
    # logger `django.request` de Django pasa el objeto de petición en
    # `extra`, y su repr es
    #     <WSGIRequest: GET '/api/v1/patients/?search=Pérez Vela'>
    # es decir, la cadena de consulta ENTERA. Ahí van apellidos de
    # pacientes. No lo atrapan las expresiones de abajo porque un apellido
    # no es ni un correo ni una ristra de dígitos: hay que tapar la clave.
    "request",
)

REDACTADO = "«redactado»"

# Correos y secuencias largas de dígitos (cédulas, teléfonos) que puedan
# haberse colado en un mensaje escrito a mano.
_CORREO = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_DIGITOS = re.compile(r"\b\d{7,}\b")


def redactar(valor):
    """
    Sustituye lo que parezca un dato personal dentro de un texto.

    Es la segunda línea de defensa, no la primera: lo que de verdad
    protege es no meter esos datos en el mensaje. Esto solo evita que un
    `logger.info(f"...{paciente.email}...")` escrito con prisa acabe en
    el agregador.
    """
    if not isinstance(valor, str):
        return valor
    valor = _CORREO.sub(REDACTADO, valor)
    return _DIGITOS.sub(REDACTADO, valor)


def limpiar_dict(datos):
    """Copia de `datos` con los valores de las claves sensibles tapados."""
    limpio = {}
    for clave, valor in (datos or {}).items():
        if any(s in str(clave).lower() for s in CLAVES_SENSIBLES):
            limpio[clave] = REDACTADO
        elif isinstance(valor, dict):
            limpio[clave] = limpiar_dict(valor)
        else:
            limpio[clave] = redactar(valor)
    return limpio


class RequestIdFilter(logging.Filter):
    """Añade `request_id` a cada registro para poder correlacionarlos."""

    def filter(self, record):
        record.request_id = get_request_id()
        return True


# Atributos que trae todo LogRecord y que no aportan nada en la salida.
_ESTANDAR = {
    "args", "asctime", "created", "exc_info", "exc_text", "filename",
    "funcName", "levelname", "levelno", "lineno", "module", "msecs",
    "message", "msg", "name", "pathname", "process", "processName",
    "relativeCreated", "stack_info", "thread", "threadName", "taskName",
}


class JsonFormatter(logging.Formatter):
    """
    Un registro por línea, en JSON.

    En JSON y no en texto porque el destino natural es un agregador
    (Cloud Logging, Loki, un `docker logs | jq`), y allí «poder filtrar
    por estado o por id de petición» vale más que «leerse bonito». Para
    la consola de desarrollo está el formato de texto, que se elige con
    `DJANGO_LOG_FORMAT=plain`.

    Lo que un `logger.info("...", extra={...})` añada aparece como claves
    de primer nivel, ya pasado por la redacción.
    """

    def format(self, record):
        salida = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": redactar(record.getMessage()),
        }
        rid = getattr(record, "request_id", "") or get_request_id()
        if rid:
            salida["request_id"] = rid

        extra = {k: v for k, v in record.__dict__.items()
                 if k not in _ESTANDAR and k != "request_id"}
        salida.update(limpiar_dict(extra))

        if record.exc_info:
            salida["exc_type"] = record.exc_info[0].__name__
            # La traza va entera: es el motivo de existir de este registro.
            # No lleva datos del paciente salvo que alguien los ponga en el
            # mensaje de una excepción, y para eso está `redactar`.
            salida["traceback"] = redactar(self.formatException(record.exc_info))

        # `default=str` para que un UUID, un Decimal o una fecha no tumben
        # el registro: perder la línea por no saber serializar un campo
        # sería el peor de los fallos posibles en un módulo de registro.
        return json.dumps(salida, ensure_ascii=False, default=str)


# Campos que hacen útil una línea de petición. Sin ellos el mensaje
# «Petición atendida» no dice absolutamente nada; con ellos se lee de un
# vistazo qué se pidió y cómo fue. Ninguno identifica a un paciente.
_UTILES = ("method", "path", "status", "duration_ms")


class PlainFormatter(logging.Formatter):
    """
    Formato legible para desarrollo, con el id de correlación delante.

    Arrastra los campos de `extra` que importan. La primera versión no lo
    hacía y en la consola solo salía «apps.request: Petición atendida»:
    correcto, correlacionable e inútil. Los datos que hacen falta para
    diagnosticar viven en `extra`, así que tienen que verse.
    """

    def format(self, record):
        rid = getattr(record, "request_id", "") or get_request_id()
        marca = f"[{rid}] " if rid else ""
        base = f"{self.formatTime(record, '%H:%M:%S')} {record.levelname:8} " \
               f"{marca}{record.name}: {redactar(record.getMessage())}"

        campos = [f"{c}={getattr(record, c)}" for c in _UTILES
                  if getattr(record, c, None) is not None]
        # El resto de `extra`, ya redactado, para no perder contexto.
        otros = limpiar_dict({
            k: v for k, v in record.__dict__.items()
            if k not in _ESTANDAR and k != "request_id" and k not in _UTILES
        })
        campos += [f"{k}={v}" for k, v in otros.items() if v is not None]
        if campos:
            base += " — " + " ".join(campos)

        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base
