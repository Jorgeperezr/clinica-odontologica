"""
El reporte financiero (Sprint 91).

Recorría los pagos uno a uno en Python acumulando en un diccionario, lo
que carga TODO el historial de la clínica en memoria y crece con él.
Medido con 9.000 pagos —tres años de una clínica pequeña— y nueve
repeticiones tras calentar:

    suma en Python   164.8 ms
    suma en SQL        6.1 ms

Lo que se fija aquí es que la respuesta **no cambió** al mover la suma:
mismas claves, mismos importes. Un informe de ingresos que cambie de
cifras por una optimización es una optimización que nadie debería
aceptar.
"""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.billing.models import Payment
from apps.common.models import Tenant
from apps.patients.models import Patient


class ElReporteFinancieroCuadraTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Caja", ruc="1790000091001")
        self.admin = User.objects.create_user(
            email="admin@caja.ec", password="superseguro123",
            role="admin", tenant=self.tenant,
        )
        self.paciente = Patient.objects.create(
            tenant=self.tenant, first_name="Ana", last_name="Vega",
            national_id="0102030411",
        )
        self.hoy = timezone.localdate()
        for dias, monto, metodo in [
            (0, "100.00", "cash"), (0, "50.50", "card"),
            (5, "20.25", "cash"), (40, "999.00", "transfer"),
        ]:
            Payment.objects.create(
                tenant=self.tenant, patient=self.paciente,
                amount=Decimal(monto), method=metodo,
                date=self.hoy - timedelta(days=dias),
            )
        self.client.force_authenticate(user=self.admin)

    def test_suma_el_total_y_lo_desglosa_por_forma_de_pago(self):
        desde = self.hoy - timedelta(days=10)
        r = self.client.get(f"/api/v1/reports/financial/?date_from={desde}&date_to={self.hoy}")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["total_income"], "170.75")   # 100 + 50.50 + 20.25
        self.assertEqual(r.data["payment_count"], 3)
        self.assertEqual(r.data["by_method"]["cash"], "120.25")
        self.assertEqual(r.data["by_method"]["card"], "50.50")
        self.assertNotIn("transfer", r.data["by_method"])

    def test_el_ultimo_dia_del_periodo_cuenta_entero(self):
        """
        El error clásico de todo informe por fechas: si el último día se
        queda fuera, la clínica consulta «este mes» y no ve lo cobrado
        hoy. Aquí no pasa porque `date` es un DateField, y conviene que
        una prueba lo sostenga si algún día cambia a fecha y hora.
        """
        r = self.client.get(
            f"/api/v1/reports/financial/?date_from={self.hoy}&date_to={self.hoy}"
        )
        self.assertEqual(r.data["payment_count"], 2)
        self.assertEqual(r.data["total_income"], "150.50")

    def test_un_periodo_sin_cobros_devuelve_cero_y_no_nulo(self):
        """
        `Sum` de un conjunto vacío es None. Sin cuidarlo, el panel
        recibiría `null` donde espera un importe y pintaría «$null».
        """
        lejos = self.hoy - timedelta(days=900)
        r = self.client.get(
            f"/api/v1/reports/financial/?date_from={lejos}&date_to={lejos}"
        )
        self.assertEqual(r.data["total_income"], "0.00")
        self.assertEqual(r.data["payment_count"], 0)
        self.assertEqual(r.data["by_method"], {})

    def test_no_se_mezclan_los_cobros_de_otra_clinica(self):
        otra = Tenant.objects.create(name="Otra", ruc="1790000091002")
        ajeno = Patient.objects.create(
            tenant=otra, first_name="X", last_name="Y", national_id="0102030412",
        )
        Payment.objects.create(
            tenant=otra, patient=ajeno, amount=Decimal("5000.00"),
            method="cash", date=self.hoy,
        )
        r = self.client.get(
            f"/api/v1/reports/financial/?date_from={self.hoy}&date_to={self.hoy}"
        )
        self.assertEqual(r.data["total_income"], "150.50")


class SePuedeLlevarAlContadorTests(ElReporteFinancieroCuadraTests):
    """
    El informe de ingresos es el que va al contador, y era el único sin
    exportación: solo el de pacientes nuevos la tenía.
    """

    def test_exporta_a_excel(self):
        desde = self.hoy - timedelta(days=10)
        r = self.client.get(
            f"/api/v1/reports/financial/?date_from={desde}&date_to={self.hoy}&export=excel"
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml", r["Content-Type"])
        self.assertIn("ingresos.xlsx", r["Content-Disposition"])
        # Un .xlsx es un zip: si no empieza por PK, no es un libro.
        self.assertTrue(r.content.startswith(b"PK"), "el archivo no es un .xlsx válido")

    def test_sin_pedir_exportacion_sigue_devolviendo_json(self):
        r = self.client.get(f"/api/v1/reports/financial/?date_to={self.hoy}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("total_income", r.data)
