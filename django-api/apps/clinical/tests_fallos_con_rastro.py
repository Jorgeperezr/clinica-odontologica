"""
Los fallos que no rompen nada, pero que hay que poder ver (Sprint 86).

El backend tenía nueve `except Exception: pass`. La decisión de no romper
el flujo es correcta en todos ellos —un fallo del almacén no puede
deshacer un tratamiento que YA SE HIZO, ni un logotipo ilegible impedir
una receta—, pero tragárselo en silencio no es ser resiliente: es no
enterarse.

El caso más caro es el inventario. Si el descuento falla y nadie lo
registra, el sistema dice que hay material y el cajón está vacío. Se
descubre abriéndolo, a mitad de un procedimiento.

Lo que se fija aquí es la combinación exacta, que es lo que importa:
**el acto clínico se conserva Y el fallo deja rastro**.
"""

import logging
from decimal import Decimal
from unittest.mock import patch

from apps.clinical.models import TreatmentPlan, TreatmentPlanItem
from apps.clinical.tests_sprint22 import Sprint22Base
from apps.common.tests_logging import _salida_real


class UnFalloDeInventarioNoSeTragaEnSilencioTests(Sprint22Base):
    def setUp(self):
        super().setUp()
        self.plan = TreatmentPlan.objects.create(
            tenant=self.tenant, patient=self.patient,
            created_by=self.doctor, status="active",
        )
        self.item = TreatmentPlanItem.objects.create(
            treatment_plan=self.plan, treatment=self.t1, order=1,
            estimated_price=Decimal("300.00"),
        )
        self.client.force_authenticate(user=self.admin)

    def _marcar_como_hecho(self):
        return self.client.patch(
            f"/api/v1/treatment-plan-items/{self.item.id}/",
            {"status": "done"}, format="json",
        )

    def test_el_tratamiento_queda_hecho_aunque_falle_el_almacen(self):
        """
        Lo que NO debe cambiar: el acto clínico se conserva. El
        tratamiento se hizo; lo que falló fue apuntar el material.
        """
        with patch("apps.inventory.services.consume_inventory_for_treatment_item",
                   side_effect=RuntimeError("almacén caído")):
            resp = self._marcar_como_hecho()

        self.assertEqual(resp.status_code, 200, resp.data)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, "done")

    def test_y_el_fallo_queda_registrado(self):
        """
        Lo que SÍ cambia: antes esto era un `pass` y no quedaba ni una
        línea. El stock se desviaba de la realidad en silencio.
        """
        with patch("apps.inventory.services.consume_inventory_for_treatment_item",
                   side_effect=RuntimeError("almacén caído")):
            with self.assertLogs("apps.clinical", level=logging.WARNING) as registro:
                self._marcar_como_hecho()

        # `registro.output` NO vale aquí: usa el formato por defecto de
        # `logging` y descarta todo lo que va en `extra`, que es justo
        # donde están los identificadores. Se pasa por el formateador de
        # producción, que es lo que de verdad se escribiría.
        completo = _salida_real(registro)
        self.assertIn("inventario", completo.lower())
        # Con el identificador del ítem se puede ir a buscar qué pasó; sin
        # él la línea diría que «algo» falló en «algún» tratamiento.
        self.assertIn(str(self.item.id), completo)
        self.assertIn("RuntimeError", completo, "falta la traza del fallo original")

    def test_si_el_almacen_responde_no_se_registra_nada(self):
        """
        No pasarse: un descuento correcto no puede dejar avisos. Un
        registro que avisa siempre es un registro que nadie lee.
        """
        with patch("apps.inventory.services.consume_inventory_for_treatment_item",
                   return_value=None):
            with self.assertNoLogs("apps.clinical", level=logging.WARNING):
                self._marcar_como_hecho()
