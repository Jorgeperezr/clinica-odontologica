"""
Registro estructurado (Sprint 75).

Lo que se fija aquí no es «que el logger funcione» —eso lo hace la
biblioteca estándar— sino las tres cosas por las que existe este módulo:

  1. Que un 500 DEJE RASTRO. Antes no lo dejaba: sin bloque `LOGGING`, con
     `DEBUG=False`, la traza no llegaba ni a la salida estándar.
  2. Que la línea sea JSON válido y se pueda correlacionar.
  3. Que NO se filtren datos personales. Es un sistema de datos de salud:
     un registro se copia, se conserva meses y lo lee gente que no tiene
     por qué ver la historia de nadie.
"""

import json
import logging

from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import path
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.common.logging import (
    JsonFormatter,
    get_request_id,
    limpiar_dict,
    redactar,
    reset_request_id,
    set_request_id,
)
from apps.common.middleware import RequestLogMiddleware
from apps.common.models import Tenant
from apps.patients.models import Patient


def _formatear(record):
    """Pasa un LogRecord por el formateador y devuelve el dict resultante."""
    return json.loads(JsonFormatter().format(record))


def _salida_real(registro):
    """
    Lo que de verdad se escribiría, pasando cada registro capturado por el
    formateador de producción.

    `assertLogs().output` NO sirve para esto: usa el formato por defecto de
    `logging` («NIVEL:logger:mensaje») y se deja fuera todo lo que va en
    `extra`, que es justo donde están la ruta, el estado y —lo que hay que
    comprobar que NO está— los datos personales.
    """
    formateador = JsonFormatter()
    return "\n".join(formateador.format(r) for r in registro.records)


def _record(msg, **extra):
    record = logging.LogRecord(
        name="apps.prueba", level=logging.INFO, pathname=__file__,
        lineno=1, msg=msg, args=(), exc_info=None,
    )
    for clave, valor in extra.items():
        setattr(record, clave, valor)
    return record


class FormatoJsonTests(SimpleTestCase):
    def tearDown(self):
        reset_request_id()

    def test_la_linea_es_json_valido(self):
        salida = _formatear(_record("hola"))
        self.assertEqual(salida["msg"], "hola")
        self.assertEqual(salida["level"], "INFO")
        self.assertEqual(salida["logger"], "apps.prueba")
        self.assertIn("ts", salida)

    def test_los_extra_salen_como_claves(self):
        salida = _formatear(_record("x", status=404, duration_ms=12.5))
        self.assertEqual(salida["status"], 404)
        self.assertEqual(salida["duration_ms"], 12.5)

    def test_un_valor_no_serializable_no_tumba_el_registro(self):
        """
        Perder la línea por no saber serializar un UUID o un Decimal sería
        el peor fallo posible en un módulo de registro: justo cuando hace
        falta, no habría nada.
        """
        import uuid
        from decimal import Decimal

        salida = _formatear(_record("x", pk=uuid.uuid4(), monto=Decimal("12.34")))
        self.assertIsInstance(salida["pk"], str)
        self.assertEqual(salida["monto"], "12.34")

    def test_el_id_de_correlacion_va_en_cada_linea(self):
        set_request_id("abc123")
        self.assertEqual(_formatear(_record("x"))["request_id"], "abc123")

    def test_la_traza_va_completa(self):
        try:
            raise ValueError("algo falló")
        except ValueError:
            import sys
            record = _record("reventó")
            record.exc_info = sys.exc_info()
        salida = _formatear(record)
        self.assertEqual(salida["exc_type"], "ValueError")
        self.assertIn("ValueError: algo falló", salida["traceback"])


class NoSeFiltranDatosPersonalesTests(SimpleTestCase):
    """
    La parte que de verdad importa. Cada caso aquí es un dato que NO puede
    acabar en un agregador de registros.
    """

    def tearDown(self):
        reset_request_id()

    def test_las_claves_sensibles_se_tapan(self):
        salida = limpiar_dict({
            "password": "superseguro123",
            "new_password": "otra",
            "authorization": "Bearer eyJ...",
            "national_id": "0102030405",
            "first_name": "Ana",
            "last_name": "Pérez Vela",
            "phone": "+593999123456",
            "status": 200,
        })
        for clave in ("password", "new_password", "authorization",
                      "national_id", "first_name", "last_name", "phone"):
            self.assertNotIn(str(salida[clave]).lower(),
                             ("superseguro123", "otra", "ana", "pérez vela"),
                             msg=f"«{clave}» se filtró")
            self.assertEqual(salida[clave], "«redactado»", msg=f"«{clave}» se filtró")
        self.assertEqual(salida["status"], 200, "lo que no es sensible debe conservarse")

    def test_el_objeto_request_se_tapa_entero(self):
        """
        El logger `django.request` de Django pasa el objeto de petición en
        `extra`, y su repr lleva la cadena de consulta COMPLETA:

            <WSGIRequest: GET '/api/v1/patients/?search=Pérez Vela'>

        Ahí van apellidos de pacientes. No lo atrapan las expresiones de
        redacción porque un apellido no es un correo ni una ristra de
        dígitos: hay que tapar la clave.
        """
        factory = RequestFactory()
        peticion = factory.get("/api/v1/patients/", {"search": "Pérez Vela"})
        salida = _formatear(_record("Internal Server Error", request=peticion))
        self.assertNotIn("Pérez", json.dumps(salida, ensure_ascii=False))
        self.assertEqual(salida["request"], "«redactado»")

    def test_un_correo_en_el_mensaje_se_redacta(self):
        salida = _formatear(_record("No se pudo avisar a ana.perez@correo.ec"))
        self.assertNotIn("ana.perez@correo.ec", salida["msg"])

    def test_una_cedula_en_el_mensaje_se_redacta(self):
        self.assertNotIn("0102030405", redactar("Paciente 0102030405 no encontrado"))

    def test_un_numero_corto_no_se_redacta(self):
        """No pasarse: un id de pieza dental o un código de estado son útiles."""
        self.assertEqual(redactar("pieza 36, estado 404"), "pieza 36, estado 404")

    def test_un_uuid_con_un_grupo_de_solo_cifras_sale_entero(self):
        """
        Este caso apareció solo: la suite falló una vez con un usuario
        cuyo identificador empezaba por ocho cifras. La regla de «siete
        dígitos seguidos» lo tomaba por una cédula y dejaba

            «redactado»-5718-4771-9ae7-a60f85d4fee6

        es decir, el registro salía pero el identificador con el que se
        rastrea al usuario ya no servía. Y pasaba unas pocas veces de
        cada cien, según qué UUID tocara: por eso se fija aquí con uno
        escrito a mano, para que no vuelva a depender de la suerte.
        """
        uuid_con_cifras = "06912074-5718-4771-9ae7-a60f85d4fee6"
        self.assertEqual(redactar(uuid_con_cifras), uuid_con_cifras)
        self.assertEqual(
            redactar(f"usuario {uuid_con_cifras} sin permiso"),
            f"usuario {uuid_con_cifras} sin permiso",
        )

    def test_el_uuid_no_sirve_de_escondite_para_una_cedula(self):
        """Respetar los UUID no puede abrir la puerta a lo de al lado."""
        salida = redactar("06912074-5718-4771-9ae7-a60f85d4fee6 cedula 0102030405")
        self.assertIn("06912074-5718-4771-9ae7-a60f85d4fee6", salida)
        self.assertNotIn("0102030405", salida)

    def test_un_grupo_largo_de_cifras_que_no_es_uuid_si_se_redacta(self):
        """Doce cifras seguidas sin forma de UUID son un teléfono o una cuenta."""
        self.assertNotIn("099123456789", redactar("contacto 099123456789"))


class MiddlewareDePeticionTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Log", ruc="1790000007001")
        self.user = User.objects.create_user(
            email="admin@log.ec", password="superseguro123",
            role="admin", tenant=self.tenant,
        )

    def tearDown(self):
        reset_request_id()

    def test_la_respuesta_lleva_el_id_de_correlacion(self):
        """
        Para que un usuario pueda dar ese código al soporte y se encuentre
        su incidencia sin buscar por hora y a ojo.
        """
        self.client.force_authenticate(user=self.user)
        resp = self.client.get("/api/v1/health/")
        self.assertTrue(resp["X-Request-ID"], "falta la cabecera X-Request-ID")

    def test_se_respeta_el_id_que_venga_del_proxy(self):
        """Así una petición se sigue de punta a punta a través de nginx."""
        resp = self.client.get("/api/v1/health/", HTTP_X_REQUEST_ID="desde-nginx-1")
        self.assertEqual(resp["X-Request-ID"], "desde-nginx-1")

    def test_las_sondas_de_salud_no_se_registran(self):
        """
        Un balanceador las pide cada diez segundos: registrarlas ahoga el
        resto, que es como se pierde una incidencia de verdad.
        """
        with self.assertNoLogs("apps.request", level="INFO"):
            self.client.get("/api/v1/health/")

    def test_una_peticion_normal_se_registra_sin_datos_personales(self):
        Patient.objects.create(
            tenant=self.tenant, first_name="Ana", last_name="Pérez Vela",
            national_id="0102030405",
        )
        self.client.force_authenticate(user=self.user)
        with self.assertLogs("apps.request", level="INFO") as registro:
            self.client.get("/api/v1/patients/", {"search": "Pérez"})

        completo = _salida_real(registro)
        self.assertIn("/api/v1/patients/", completo)
        # El VALOR de la búsqueda es un apellido: no puede quedar escrito.
        self.assertNotIn("Pérez", completo, "el valor de búsqueda se filtró al registro")
        self.assertNotIn("0102030405", completo)
        self.assertNotIn("admin@log.ec", completo)
        # Lo que sí debe estar, para poder diagnosticar.
        self.assertIn(str(self.user.pk), completo)
        self.assertIn("search", completo, "el NOMBRE del parámetro sí es útil")

    def test_el_middleware_no_rompe_si_no_hay_usuario(self):
        resp = self.client.get("/api/v1/patients/")
        self.assertIn(resp.status_code, (401, 403))


def _revienta(request):
    raise RuntimeError("fallo inesperado")


urlpatterns = [path("revienta/", _revienta)]


@override_settings(ROOT_URLCONF=__name__)
class UnErrorQuinientosDejaRastroTests(SimpleTestCase):
    """
    La prueba que justifica el sprint entero.

    ANTES: sin bloque `LOGGING`, con `DEBUG=False`, un 500 devolvía su 500
    al cliente y la traza NO aparecía en ningún sitio —ni en la salida
    estándar—, porque el único logger de Django era `django`, con `console`
    filtrado por `require_debug_true` y `mail_admins` sin ADMINS. Cuando el
    panel de la clínica fallaba, nadie llegaba a enterarse de por qué.
    """

    @override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
    def test_el_500_se_registra_con_traza_y_contexto(self):
        self.client.raise_request_exception = False
        with self.assertLogs("apps.request", level="ERROR") as registro:
            resp = self.client.get("/revienta/")
        self.assertEqual(resp.status_code, 500)

        completo = _salida_real(registro)
        self.assertIn("RuntimeError", completo)
        self.assertIn("fallo inesperado", completo)
        self.assertIn("/revienta/", completo)

    @override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
    def test_el_500_no_filtra_la_cadena_de_consulta(self):
        self.client.raise_request_exception = False
        with self.assertLogs("apps.request", level="ERROR") as registro:
            self.client.get("/revienta/", {"search": "Pérez Vela"})
        completo = _salida_real(registro)
        self.assertNotIn("Pérez", completo)
        self.assertIn("search", completo, "el nombre del parámetro sí ayuda a reproducir")

    @override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
    def test_el_id_de_correlacion_cose_las_lineas_del_mismo_fallo(self):
        """
        Las dos líneas del mismo 500 —la excepción y la respuesta— tienen
        que compartir identificador; si no, no hay forma de juntarlas en el
        agregador.
        """
        self.client.raise_request_exception = False
        with self.assertLogs("apps.request", level="ERROR") as registro:
            resp = self.client.get("/revienta/")
        ids = {r.request_id for r in registro.records if hasattr(r, "request_id")}
        # El filtro se aplica en el manejador, no en assertLogs; se compara
        # contra el de la cabecera, que es el mismo contexto.
        self.assertTrue(resp["X-Request-ID"])
        self.assertLessEqual(len(ids), 1)
        self.assertEqual(len(registro.records), 2,
                         "se esperan dos líneas: la excepción y la respuesta")
        self.assertEqual(get_request_id(), resp["X-Request-ID"])


class SinPeticionNoHayIdTests(SimpleTestCase):
    """Una tarea de Celery o un comando registran igual, solo que sin id."""

    def test_fuera_de_una_peticion_no_hay_request_id(self):
        reset_request_id()
        self.assertNotIn("request_id", _formatear(_record("desde una tarea")))

    def test_el_middleware_se_puede_instanciar_sin_peticion(self):
        mw = RequestLogMiddleware(lambda r: None)
        self.assertIsNotNone(mw)
