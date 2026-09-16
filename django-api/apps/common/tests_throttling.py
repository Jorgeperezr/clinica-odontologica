"""
Límite de peticiones (Sprint 81).

Lo que se fija aquí no es «que DRF sepa limitar» —eso es la biblioteca—
sino el equilibrio concreto entre dos cosas que tiran en sentidos
opuestos:

  1. Que el panel se pueda USAR. El límite anterior, 60/min, se agotaba
     abriendo una o dos fichas clínicas, y al agotarse la pestaña de
     planes se quedaba en blanco. Medido con un navegador de verdad, no
     supuesto.
  2. Que el login siga protegido contra fuerza bruta. Subir el cupo del
     usuario autenticado no puede aflojar eso, porque quien lo protege
     es el límite de anónimo.

Las dos pruebas de abajo son las dos mitades. Si alguien «ordena» estos
números más adelante, una de ellas se pondrá roja.
"""

from unittest.mock import patch

from django.core.cache import cache
from rest_framework.test import APITestCase
from rest_framework.throttling import UserRateThrottle

from apps.accounts.models import User
from apps.common.models import Tenant

# Lo que cuesta abrir una ficha clínica y mirar sus pestañas, contado en
# el navegador: unas treinta peticiones. Se prueba con más margen porque
# nadie abre exactamente una ficha y se detiene.
PETICIONES_DE_UNA_FICHA = 45


class ElPanelSePuedeUsarTests(APITestCase):
    """Que el límite no bloquee el trabajo normal de una clínica."""

    def setUp(self):
        # El contador vive en la caché y sobrevive entre pruebas: sin
        # esto, el resultado depende de qué se haya ejecutado antes.
        cache.clear()
        self.tenant = Tenant.objects.create(name="Clínica Cupo", ruc="1790000081001")
        self.user = User.objects.create_user(
            email="recepcion@cupo.ec", password="x", role="admin", tenant=self.tenant,
        )
        self.client.force_authenticate(user=self.user)

    def test_abrir_una_ficha_entera_no_agota_el_cupo(self):
        """
        Con 60/min esto fallaba por la mitad. Y no era un caso raro: es
        lo que hace una recepcionista con el segundo paciente del día.
        """
        for numero in range(1, PETICIONES_DE_UNA_FICHA + 1):
            resp = self.client.get("/api/v1/patients/")
            self.assertNotEqual(
                resp.status_code, 429,
                f"bloqueado en la petición {numero} de {PETICIONES_DE_UNA_FICHA}: "
                "el límite vuelve a estar por debajo de lo que cuesta usar el panel",
            )

    def test_el_limite_sigue_existiendo(self):
        """
        Una prueba que no puede fallar no prueba nada: con el cupo bajado
        a tres, el 429 tiene que aparecer. Así se sabe que la de arriba
        pasa por el límite y no porque el mecanismo esté apagado.

        Se parchea la tasa en la CLASE y no con `override_settings`, que
        aquí no sirve: DRF copia las tasas a `THROTTLE_RATES` al importar
        el módulo, así que cambiar el ajuste después no llega a nadie. Se
        descubrió porque esta misma prueba pasaba con seis 200 seguidos.
        """
        with patch.dict(UserRateThrottle.THROTTLE_RATES, {"user": "3/min"}):
            codigos = [self.client.get("/api/v1/patients/").status_code
                       for _ in range(6)]
        self.assertIn(429, codigos, "el limitador no está actuando en absoluto")


class ElLoginSigueProtegidoTests(APITestCase):
    """
    Subir el cupo del usuario autenticado no puede abrir la puerta a
    probar contraseñas a mansalva. Quien frena eso es el límite de
    anónimo, que es otro y no se ha tocado.
    """

    def setUp(self):
        cache.clear()
        self.tenant = Tenant.objects.create(name="Clínica Puerta", ruc="1790000082001")
        User.objects.create_user(
            email="admin@puerta.ec", password="la-buena", role="admin",
            tenant=self.tenant,
        )

    def test_probar_contrasenas_a_ciegas_se_corta(self):
        bloqueado = False
        for _ in range(40):
            resp = self.client.post(
                "/api/v1/auth/login/",
                {"email": "admin@puerta.ec", "password": "no-es-esta"},
                format="json",
            )
            if resp.status_code == 429:
                bloqueado = True
                break
        self.assertTrue(
            bloqueado,
            "se pudieron probar 40 contraseñas seguidas sin que nadie lo cortara",
        )
