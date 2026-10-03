"""
El precio que ve el paciente y el que se le cobra (Sprint 84).

Encontrado recorriendo el panel con un navegador, no leyendo código: a una
paciente con convenio, el plan de tratamiento sumaba **580** y el
presupuesto generado desde ese mismo plan cobraba **413**. Las dos cifras
salían de la misma pantalla con un clic de diferencia, y la que el
odontólogo lee en voz alta delante del paciente es la primera.

El presupuesto tenía razón —413 es 180 menos el 15 % del convenio, más una
corona con tarifa pactada de 260—. Lo que estaba mal era el plan, que se
sembraba con el precio de catálogo.

Lo que se fija aquí:

  1. Que el plan nazca con el precio del PACIENTE.
  2. Que plan y presupuesto digan lo mismo.
  3. Que un precio pactado a mano sobreviva al presupuesto.
  4. Que cambiar de convenio actualice lo que puso el sistema y respete lo
     que pactó una persona.
"""

from decimal import Decimal

from apps.clinical.models import (
    TreatmentPlan,
    TreatmentPlanItem,
    TreatmentPlanTemplate,
    TreatmentPlanTemplateItem,
)
from apps.clinical.tests_sprint22 import Sprint22Base
from apps.configuration.models import Agreement, Tariff


class ElPlanUsaElPrecioDelPacienteTests(Sprint22Base):
    def setUp(self):
        super().setUp()
        # Convenio con 20 % de descuento y, además, una tarifa pactada
        # para la corona: los dos caminos de `pricing.py` en un solo caso.
        self.convenio = Agreement.objects.create(
            tenant=self.tenant, name="Seguros Prueba",
            discount_percentage=Decimal("20.00"),
        )
        Tariff.objects.create(
            tenant=self.tenant, treatment=self.t1, agreement=self.convenio,
            price=Decimal("200.00"),
        )
        self.patient.agreement = self.convenio
        self.patient.save(update_fields=["agreement"])

        self.plantilla = TreatmentPlanTemplate.objects.create(
            tenant=self.tenant, name="Protocolo de prueba",
        )
        for orden, tratamiento in enumerate((self.t1, self.t2), start=1):
            TreatmentPlanTemplateItem.objects.create(
                template=self.plantilla, treatment=tratamiento, order=orden,
            )
        self.client.force_authenticate(user=self.admin)

    def _aplicar(self):
        resp = self.client.post(
            f"/api/v1/patients/{self.patient.id}/apply-plan-template/",
            {"template_id": str(self.plantilla.id)}, format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        return TreatmentPlan.objects.get(id=resp.data["id"])

    def test_el_plan_nace_con_el_precio_del_convenio(self):
        """
        Corona: tarifa pactada, 200 y no 300.
        Limpieza: sin tarifa, 50 menos el 20 % = 40.
        """
        plan = self._aplicar()
        precios = {i.treatment.name: i.estimated_price for i in plan.items.all()}
        self.assertEqual(precios["Corona S22"], Decimal("200.00"))
        self.assertEqual(precios["Limpieza S22"], Decimal("40.00"))

    def test_el_plan_y_el_presupuesto_dicen_lo_mismo(self):
        """
        El fallo original en una sola aserción: eran 580 contra 413.
        """
        plan = self._aplicar()
        total_del_plan = sum(i.estimated_price for i in plan.items.all())

        resp = self.client.post(f"/api/v1/treatment-plans/{plan.id}/generate-budget/")
        self.assertIn(resp.status_code, (200, 201), resp.data)
        total_presupuestado = Decimal(str(resp.data["total_amount"]))

        self.assertEqual(
            total_del_plan, total_presupuestado,
            "el plan y el presupuesto vuelven a decir cifras distintas: "
            "la que se lee en voz alta al paciente es la del plan",
        )

    def test_sin_convenio_se_cobra_el_catalogo(self):
        """No pasarse: un paciente particular paga la tarifa normal."""
        self.patient.agreement = None
        self.patient.save(update_fields=["agreement"])
        plan = self._aplicar()
        precios = {i.treatment.name: i.estimated_price for i in plan.items.all()}
        self.assertEqual(precios["Corona S22"], Decimal("300.00"))
        self.assertEqual(precios["Limpieza S22"], Decimal("50.00"))


class UnPrecioPactadoAManoNoSeToca(Sprint22Base):
    """
    La otra mitad: si el odontólogo acuerda una cifra con el paciente, el
    tarifario no puede reescribírsela por detrás.
    """

    def setUp(self):
        super().setUp()
        self.convenio = Agreement.objects.create(
            tenant=self.tenant, name="Convenio Mano", discount_percentage=Decimal("10.00"),
        )
        self.patient.agreement = self.convenio
        self.patient.save(update_fields=["agreement"])
        self.plan = TreatmentPlan.objects.create(
            tenant=self.tenant, patient=self.patient, created_by=self.doctor, status="active",
        )
        self.item = TreatmentPlanItem.objects.create(
            treatment_plan=self.plan, treatment=self.t1, order=1,
            estimated_price=Decimal("300.00"),
        )
        self.client.force_authenticate(user=self.admin)

    def test_editar_el_precio_lo_deja_fijado(self):
        resp = self.client.patch(
            f"/api/v1/treatment-plan-items/{self.item.id}/",
            {"estimated_price": "111.00"}, format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.item.refresh_from_db()
        self.assertTrue(self.item.price_is_manual)

        resp = self.client.post(f"/api/v1/treatment-plans/{self.plan.id}/generate-budget/")
        self.assertEqual(
            Decimal(str(resp.data["total_amount"])), Decimal("111.00"),
            "el convenio reescribió un precio que había pactado una persona",
        )

    def test_cambiar_de_estado_no_fija_el_precio(self):
        """
        Un PATCH que solo mueve el estado no puede congelar el precio de
        rebote: seguiría el del tarifario.
        """
        resp = self.client.patch(
            f"/api/v1/treatment-plan-items/{self.item.id}/",
            {"status": "in_progress"}, format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.item.refresh_from_db()
        self.assertFalse(self.item.price_is_manual)

    def test_si_el_paciente_cambia_de_convenio_el_precio_del_sistema_le_sigue(self):
        """
        El caso que hizo falta un campo explícito. Con la regla vieja
        —«automático si coincide con el catálogo»— un plan sembrado al
        precio del convenio dejaba de parecer automático, y al cambiar el
        paciente de convenio conservaba el importe antiguo.
        """
        otro = Agreement.objects.create(
            tenant=self.tenant, name="Convenio Nuevo", discount_percentage=Decimal("50.00"),
        )
        self.patient.agreement = otro
        self.patient.save(update_fields=["agreement"])

        resp = self.client.post(f"/api/v1/treatment-plans/{self.plan.id}/generate-budget/")
        self.assertEqual(
            Decimal(str(resp.data["total_amount"])), Decimal("150.00"),
            "el presupuesto no siguió al convenio nuevo del paciente",
        )


class AnadirUnaLineaConPrecioPactadoTests(Sprint22Base):
    """
    El hueco que dejó la primera versión de este cambio, y que cazó una
    prueba del Sprint 71 que ya existía: marcar el precio al EDITAR no
    basta si al CREAR la línea no se marca también. Añadir un
    procedimiento con una cifra acordada y presupuestar después la
    reescribía con la tarifa del convenio.
    """

    def setUp(self):
        super().setUp()
        self.convenio = Agreement.objects.create(
            tenant=self.tenant, name="Convenio Alta", discount_percentage=Decimal("30.00"),
        )
        self.patient.agreement = self.convenio
        self.patient.save(update_fields=["agreement"])
        self.plan = TreatmentPlan.objects.create(
            tenant=self.tenant, patient=self.patient, created_by=self.doctor, status="active",
        )
        self.client.force_authenticate(user=self.admin)

    def test_una_linea_creada_con_precio_lo_conserva(self):
        resp = self.client.post(
            f"/api/v1/treatment-plans/{self.plan.id}/items/",
            {"treatment": str(self.t1.id), "estimated_price": "99.00", "order": 1},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(TreatmentPlanItem.objects.get(id=resp.data["id"]).price_is_manual)

        resp = self.client.post(f"/api/v1/treatment-plans/{self.plan.id}/generate-budget/")
        self.assertEqual(
            Decimal(str(resp.data["total_amount"])), Decimal("99.00"),
            "el convenio pisó un precio acordado al añadir la línea",
        )

    def test_una_linea_creada_sin_precio_sigue_al_tarifario(self):
        """Lo contrario: sin precio en la petición, manda el convenio."""
        resp = self.client.post(
            f"/api/v1/treatment-plans/{self.plan.id}/items/",
            {"treatment": str(self.t1.id), "order": 1}, format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertFalse(TreatmentPlanItem.objects.get(id=resp.data["id"]).price_is_manual)

        resp = self.client.post(f"/api/v1/treatment-plans/{self.plan.id}/generate-budget/")
        self.assertEqual(
            Decimal(str(resp.data["total_amount"])), Decimal("210.00"),
            "300 menos el 30 % del convenio",
        )
