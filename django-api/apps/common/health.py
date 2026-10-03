"""
Comprobación de salud del servicio (Sprint 72).

El gateway de WhatsApp tenía `/health` desde el primer día; Django no
tenía ninguno. Eso deja sin respuesta a quien necesita saber si el
servicio está vivo y no puede autenticarse para preguntarlo: el
`healthcheck` de Docker, la sonda de un balanceador, el monitor de
disponibilidad, o un guion de arranque esperando a que el servidor
levante. Sin endpoint, todos acaban usando algo que no significa lo que
parece —normalmente `/admin/login/`, que responde 200 aunque la base de
datos esté caída, porque esa página no la consulta—.

Se exponen DOS rutas, porque son dos preguntas distintas y confundirlas
es la causa habitual de los reinicios en cascada:

  /api/v1/health/  — «¿está el proceso vivo?» (liveness). No toca la
      base de datos. Si esto falla, el proceso está colgado y reiniciarlo
      arregla algo.

  /api/v1/ready/   — «¿puede atender peticiones?» (readiness). Comprueba
      la base de datos. Si esto falla, el proceso está bien pero le falta
      una dependencia: hay que sacarlo del balanceador, NO reiniciarlo.
      Reiniciar procesos sanos porque la base de datos tiene un mal
      momento convierte una incidencia en una caída.

Qué se devuelve, y qué no. Ambas son públicas y sin autenticación —un
monitor no tiene credenciales—, así que no dicen ni la versión, ni el
motor de base de datos, ni el nombre de la clínica, ni ninguna cuenta.
Un atacante que las encuentre solo aprende que hay algo escuchando, cosa
que ya sabía por haber llegado hasta aquí.
"""

import logging

from django.db import connection
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class HealthView(APIView):
    """GET /api/v1/health/ — el proceso responde. No consulta nada."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []   # ver la nota de ReadyView

    def get(self, request):
        return Response({"status": "ok"})


class ReadyView(APIView):
    """
    GET /api/v1/ready/ — el servicio puede atender: la base de datos
    responde. Devuelve 503 cuando no, que es lo que un balanceador
    entiende como «no me mandes tráfico».

    **Sin límite de peticiones**, y no por comodidad. Estas dos rutas son
    anónimas, así que caían en el cupo de anónimo (20/min por IP), el
    mismo que comparte todo el tráfico sin autenticar. Un balanceador
    sondea cada diez segundos desde una sola IP: basta con que coincida
    con cualquier otra cosa anónima para agotarlo, y entonces la sonda
    recibe un 429. Un 429 no es «estoy sano»: el balanceador saca de
    rotación un servidor que estaba perfectamente bien, que es justo el
    desastre que esta ruta existe para evitar. No hay nada que proteger
    aquí —`health` no consulta nada y `ready` hace un SELECT 1—, mientras
    que quien sí necesita el cupo de anónimo es el login.

    Apareció en el CI: la suite entera corre en once segundos, así que
    todas las peticiones anónimas de todas las pruebas caen dentro de la
    misma ventana de un minuto y estas dos se quedaban sin cupo.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception:
            # El detalle va al registro, no a la respuesta: el mensaje de
            # error de la base de datos lleva host, puerto y usuario.
            logger.exception("Comprobación de disponibilidad fallida")
            return Response(
                {"status": "unavailable", "database": "error"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"status": "ok", "database": "ok"})
