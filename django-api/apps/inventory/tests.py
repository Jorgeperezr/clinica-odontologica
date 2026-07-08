from datetime import date, timedelta
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.agenda.models import Doctor
from apps.common.models import Tenant
from apps.configuration.models import Treatment, TreatmentInventoryItem
from apps.inventory.models import Batch, InventoryMovement, Product
from apps.patients.models import Patient
from apps.specialties.models import Specialty


class InventoryTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Test", ruc="1234567890001")
        self.auxiliary = User.objects.create_user(
            email="aux@test.com", password="superseguro123", role="auxiliary", tenant=self.tenant
        )
        self.doctor_user = User.objects.create_user(
            email="doc@test.com", password="superseguro123", role="doctor", tenant=self.tenant
        )
        self.admin = User.objects.create_user(
            email="admin@test.com", password="superseguro123", role="admin", tenant=self.tenant
        )

    def test_create_product(self):
        self.client.force_authenticate(user=self.auxiliary)
        resp = self.client.post(
            reverse("product-list"),
            {"name": "Anestesia", "unit": "ml", "min_stock": "10"},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_add_batch_creates_movement(self):
        product = Product.objects.create(tenant=self.tenant, name="Guantes", min_stock=Decimal("5"))
        self.client.force_authenticate(user=self.auxiliary)
        resp = self.client.post(
            reverse("batch-list", kwargs={"pk": product.id}),
            {"product": str(product.id), "batch_number": "L001", "quantity": "100",
             "expiration_date": "2027-01-01"},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # El ingreso del lote debe registrar un movimiento de entrada
        self.assertTrue(
            InventoryMovement.objects.filter(product=product, movement_type="in").exists()
        )

    def test_current_stock_sums_batches(self):
        product = Product.objects.create(tenant=self.tenant, name="Gasa", min_stock=Decimal("5"))
        Batch.objects.create(tenant=self.tenant, product=product, batch_number="A", quantity=Decimal("30"))
        Batch.objects.create(tenant=self.tenant, product=product, batch_number="B", quantity=Decimal("20"))
        self.assertEqual(product.current_stock, Decimal("50"))

    def test_low_stock_alert(self):
        product = Product.objects.create(tenant=self.tenant, name="Agujas", min_stock=Decimal("50"))
        Batch.objects.create(tenant=self.tenant, product=product, batch_number="X", quantity=Decimal("10"))
        self.client.force_authenticate(user=self.auxiliary)
        resp = self.client.get(reverse("low-stock-alert"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["low_stock_products"]), 1)

    def test_expiring_alert(self):
        product = Product.objects.create(tenant=self.tenant, name="Composite", min_stock=Decimal("1"))
        Batch.objects.create(
            tenant=self.tenant, product=product, batch_number="EXP",
            quantity=Decimal("5"), expiration_date=date.today() + timedelta(days=15),
        )
        self.client.force_authenticate(user=self.auxiliary)
        resp = self.client.get(reverse("expiring-alert"), {"days": 30})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["expiring_batches"]), 1)


class AutoConsumptionTests(APITestCase):
    """Descuento automático de inventario al completar un tratamiento (RF-INV-05)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Test", ruc="1234567890001")
        self.doctor_user = User.objects.create_user(
            email="doc@test.com", password="superseguro123", role="doctor", tenant=self.tenant
        )
        self.doctor = Doctor.objects.create(tenant=self.tenant, user=self.doctor_user)
        self.patient = Patient.objects.create(
            tenant=self.tenant, first_name="Test", last_name="Paciente", national_id="1515151515"
        )
        self.specialty = Specialty.objects.create(tenant=self.tenant, name="Clínica general")
        self.treatment = Treatment.objects.create(
            tenant=self.tenant, name="Restauración", specialty=self.specialty,
            base_price="80.00", consumes_inventory=True,
        )
        # Producto con stock y vínculo con el tratamiento
        self.product = Product.objects.create(
            tenant=self.tenant, name="Resina", min_stock=Decimal("2")
        )
        Batch.objects.create(
            tenant=self.tenant, product=self.product, batch_number="R1", quantity=Decimal("10"),
        )
        TreatmentInventoryItem.objects.create(
            treatment=self.treatment,
            product=self.product, quantity_used=Decimal("3"),
        )

    def test_completing_treatment_discounts_stock(self):
        from apps.clinical.models import TreatmentPlan, TreatmentPlanItem

        plan = TreatmentPlan.objects.create(
            tenant=self.tenant, patient=self.patient, created_by=self.doctor
        )
        item = TreatmentPlanItem.objects.create(
            treatment_plan=plan, treatment=self.treatment, order=1
        )
        # Stock inicial: 10
        self.assertEqual(self.product.current_stock, Decimal("10"))

        # Marcar el ítem como realizado vía API
        self.client.force_authenticate(user=self.doctor_user)
        resp = self.client.patch(
            reverse("treatment-plan-item-update", kwargs={"pk": item.id}),
            {"status": "done"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Stock debe haber bajado en 3 (10 - 3 = 7)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, Decimal("7"))
        # Debe existir un movimiento de consumo
        self.assertTrue(
            InventoryMovement.objects.filter(
                product=self.product, reason="consumption"
            ).exists()
        )


class ReportExportTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Test", ruc="1234567890001")
        self.admin = User.objects.create_user(
            email="admin@test.com", password="superseguro123", role="admin", tenant=self.tenant
        )
        Patient.objects.create(
            tenant=self.tenant, first_name="Nuevo", last_name="Paciente", national_id="1616161616"
        )

    def test_new_patients_report_json(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(reverse("report-new-patients"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)

    def test_new_patients_report_excel(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(reverse("report-new-patients"), {"export": "excel"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Debe ser un archivo xlsx (empieza con PK, firma de ZIP)
        self.assertTrue(resp.content.startswith(b"PK"))
        self.assertIn("spreadsheetml", resp["Content-Type"])
