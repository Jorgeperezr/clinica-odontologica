"""
QA integral (Sprint 17): prueba end-to-end que simula el flujo completo
de una clínica real a través de TODOS los módulos, usando la API como
lo haría el panel web. Los bugs de integración entre módulos viven aquí,
no en los tests unitarios de cada app.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.agenda.models import Doctor
from apps.common.models import Tenant


class FullClinicFlowTest(APITestCase):
    """Un día en la clínica: del registro del paciente al reporte final."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica E2E", ruc="9999999999001")
        from django.core.management import call_command
        call_command("bootstrap", tenant_name=self.tenant.name)

        self.admin = User.objects.create_user(
            email="admin@e2e.ec", password="superseguro123", role="admin",
            tenant=self.tenant, full_name="Admin E2E",
        )
        self.reception = User.objects.create_user(
            email="recep@e2e.ec", password="superseguro123", role="reception",
            tenant=self.tenant, full_name="Recepción E2E",
        )
        doctor_user = User.objects.create_user(
            email="doc@e2e.ec", password="superseguro123", role="doctor",
            tenant=self.tenant, full_name="Dra. E2E",
        )
        self.doctor = Doctor.objects.create(tenant=self.tenant, user=doctor_user)
        self.doctor_user = doctor_user

    def test_full_clinic_flow(self):
        # ── 1. Recepción registra al paciente ──
        self.client.force_authenticate(user=self.reception)
        resp = self.client.post("/api/v1/patients/", {
            "first_name": "Elena", "last_name": "Torres",
            "national_id": "0999000111", "phone": "+593987654321",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)
        patient_id = resp.data["id"]

        # Opt-in de WhatsApp
        resp = self.client.post(f"/api/v1/patients/{patient_id}/whatsapp-optin/", {
            "patient": patient_id, "channel": "registro_recepcion",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)

        # ── 2. Admin configura el catálogo ──
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post("/api/v1/specialties/", {"name": "Rehabilitación E2E"})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)
        specialty_id = resp.data["id"]

        resp = self.client.post("/api/v1/config/treatments/", {
            "name": "Corona E2E", "specialty": specialty_id,
            "base_price": "300.00", "consumes_inventory": True,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)
        treatment_id = resp.data["id"]

        # Inventario: producto + lote + vínculo tratamiento→insumo
        resp = self.client.post("/api/v1/products/", {
            "name": "Cemento E2E", "unit": "unidad", "min_stock": "2",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)
        product_id = resp.data["id"]

        resp = self.client.post(f"/api/v1/products/{product_id}/batches/", {
            "product": product_id, "batch_number": "E2E-1", "quantity": "10",
            "expiration_date": str(date.today() + timedelta(days=365)),
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)

        from apps.configuration.models import Treatment, TreatmentInventoryItem
        from apps.inventory.models import Product
        TreatmentInventoryItem.objects.create(
            treatment=Treatment.objects.get(id=treatment_id),
            product=Product.objects.get(id=product_id),
            quantity_used=Decimal("2"),
        )

        # ── 3. Presupuesto → aprobación → plan de cuotas ──
        self.client.force_authenticate(user=self.reception)
        resp = self.client.post(f"/api/v1/patients/{patient_id}/budgets/", {
            "patient": patient_id, "notes": "Presupuesto E2E",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)
        budget_id = resp.data["id"]

        resp = self.client.post(f"/api/v1/budgets/{budget_id}/items/", {
            "treatment": treatment_id, "tooth_fdi_code": "16",
            "quantity": 1, "unit_price": "300.00",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)

        resp = self.client.post(f"/api/v1/budgets/{budget_id}/approve/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)

        resp = self.client.post(f"/api/v1/budgets/{budget_id}/generate-payment-plan/", {
            "installment_count": 3, "first_due_date": str(date.today() - timedelta(days=60)),
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)
        installments = resp.data["installments"]
        self.assertEqual(len(installments), 3)
        total = sum(Decimal(i["amount"]) for i in installments)
        self.assertEqual(total, Decimal("300.00"))  # reparto exacto

        # El presupuesto ahora expone su payment_plan_id (para el panel)
        resp = self.client.get(f"/api/v1/budgets/{budget_id}/")
        self.assertIsNotNone(resp.data["payment_plan_id"])

        # ── 4. Bloqueo por morosidad (primera cuota venció hace 60 días) ──
        start = timezone.now() + timedelta(days=1)
        payload = {
            "patient": patient_id, "doctor": str(self.doctor.id),
            "scheduled_start": start.isoformat(),
            "scheduled_end": (start + timedelta(minutes=30)).isoformat(),
        }
        resp = self.client.post("/api/v1/appointments/", payload)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT, resp.content)
        self.assertEqual(resp.data["error"]["code"], "patient_delinquent")

        # Excepción manual (override)
        resp = self.client.post("/api/v1/appointments/", {**payload, "override": "true"})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)
        appointment_id = resp.data["id"]

        # ── 5. Cobro de la deuda → el bloqueo desaparece ──
        for inst in installments:
            resp = self.client.post(f"/api/v1/installments/{inst['id']}/pay/", {
                "amount": inst["amount"], "method": "cash",
            })
            self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)

        resp = self.client.get(f"/api/v1/patients/{patient_id}/account-statement/")
        self.assertEqual(resp.data["balance"], "0.00")
        self.assertEqual(resp.data["overdue_count"], 0)

        # Ahora una segunda cita se crea SIN override
        start2 = timezone.now() + timedelta(days=2)
        resp = self.client.post("/api/v1/appointments/", {
            "patient": patient_id, "doctor": str(self.doctor.id),
            "scheduled_start": start2.isoformat(),
            "scheduled_end": (start2 + timedelta(minutes=30)).isoformat(),
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)

        # ── 6. Atención: confirmar → check-in → clínico → check-out ──
        resp = self.client.post(f"/api/v1/appointments/{appointment_id}/confirm/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        resp = self.client.post(f"/api/v1/appointments/{appointment_id}/checkin/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)

        # El doctor registra la parte clínica
        self.client.force_authenticate(user=self.doctor_user)
        resp = self.client.post(f"/api/v1/patients/{patient_id}/evolutions/", {
            "type": "clinical_note", "date": str(date.today()),
            "notes": "Paciente atendida. Corona en 16.",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)
        self.assertEqual(resp.data["registered_by"], "Dra. E2E")

        # Odontograma: registrar estado
        resp = self.client.get("/api/v1/odontogram-states/")
        state_id = next(s["id"] for s in resp.data if s["code"] == "CORONA")
        resp = self.client.post(f"/api/v1/patients/{patient_id}/tooth-records/", {
            "tooth_fdi_code": "16", "surface": "whole",
            "state": state_id, "date": str(date.today()),
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)

        resp = self.client.get(f"/api/v1/patients/{patient_id}/odontogram/current/")
        self.assertEqual(len(resp.data["teeth"]), 1)
        self.assertEqual(resp.data["teeth"][0]["state_code"], "CORONA")

        # Plan de tratamiento → ítem realizado → inventario descontado
        resp = self.client.post(f"/api/v1/patients/{patient_id}/treatment-plans/", {
            "status": "active", "notes": "Plan E2E",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)
        plan_id = resp.data["id"]

        resp = self.client.post(f"/api/v1/treatment-plans/{plan_id}/items/", {
            "treatment": treatment_id, "tooth_fdi_code": "16",
            "order": 1, "estimated_price": "300.00",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)
        item_id = resp.data["id"]

        resp = self.client.patch(f"/api/v1/treatment-plan-items/{item_id}/", {"status": "done"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)

        product = Product.objects.get(id=product_id)
        self.assertEqual(product.current_stock, Decimal("8"))  # 10 - 2 consumidas

        # Check-out
        self.client.force_authenticate(user=self.reception)
        resp = self.client.post(f"/api/v1/appointments/{appointment_id}/checkout/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)

        # ── 7. Reportes del admin reflejan todo ──
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get("/api/v1/reports/financial/")
        self.assertEqual(resp.data["total_income"], "300.00")
        self.assertEqual(resp.data["by_method"]["cash"], "300.00")

        resp = self.client.get("/api/v1/reports/delinquency/")
        self.assertEqual(len(resp.data["patients"]), 0)  # deuda saldada

        resp = self.client.get("/api/v1/reports/new-patients/")
        self.assertEqual(resp.data["count"], 1)

        # Export Excel funciona (firma ZIP)
        resp = self.client.get("/api/v1/reports/inventory/?export=excel")
        self.assertTrue(resp.content.startswith(b"PK"))

        # Export de historia clínica a PDF
        self.client.force_authenticate(user=self.doctor_user)
        resp = self.client.get(f"/api/v1/patients/{patient_id}/clinical-record/export-pdf/")
        self.assertTrue(resp.content.startswith(b"%PDF"))
