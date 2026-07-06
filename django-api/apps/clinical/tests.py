from datetime import date

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import AuditLog, User
from apps.agenda.models import Doctor
from apps.clinical.models import Evolution, TreatmentPlan
from apps.common.models import Tenant
from apps.configuration.models import Treatment
from apps.patients.models import Patient
from apps.specialties.models import Specialty


class ClinicalTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Test", ruc="1234567890001")
        self.doctor_user = User.objects.create_user(
            email="doc@test.com", password="superseguro123", role="doctor", tenant=self.tenant
        )
        self.doctor = Doctor.objects.create(tenant=self.tenant, user=self.doctor_user)
        self.reception = User.objects.create_user(
            email="recep@test.com", password="superseguro123", role="reception", tenant=self.tenant
        )
        self.patient = Patient.objects.create(
            tenant=self.tenant, first_name="María", last_name="Pérez", national_id="0102030405"
        )
        self.specialty = Specialty.objects.create(tenant=self.tenant, name="Endodoncia")
        self.treatment = Treatment.objects.create(
            tenant=self.tenant, name="Tratamiento de conducto",
            specialty=self.specialty, base_price="200.00",
        )

    def test_doctor_creates_evolution(self):
        self.client.force_authenticate(user=self.doctor_user)
        resp = self.client.post(
            reverse("evolution-list", kwargs={"pk": self.patient.id}),
            {"type": "clinical_note", "date": str(date.today()), "notes": "Paciente con dolor."},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Evolution.objects.count(), 1)

    def test_reception_cannot_access_clinical(self):
        self.client.force_authenticate(user=self.reception)
        resp = self.client.get(reverse("evolution-list", kwargs={"pk": self.patient.id}))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_clinical_access_is_audited(self):
        self.client.force_authenticate(user=self.doctor_user)
        self.client.get(reverse("clinical-record", kwargs={"pk": self.patient.id}))
        self.assertTrue(
            AuditLog.objects.filter(entity_type="ClinicalRecord", entity_id=str(self.patient.id)).exists()
        )

    def test_prescription_visible_to_patient_flag(self):
        self.client.force_authenticate(user=self.doctor_user)
        resp = self.client.post(
            reverse("evolution-list", kwargs={"pk": self.patient.id}),
            {"type": "prescription", "date": str(date.today()),
             "notes": "Ibuprofeno 400mg", "visible_to_patient": True},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        evo = Evolution.objects.get()
        self.assertTrue(evo.visible_to_patient)
        self.assertEqual(evo.type, "prescription")

    def test_create_treatment_plan_with_item(self):
        self.client.force_authenticate(user=self.doctor_user)
        # Crear plan
        resp = self.client.post(
            reverse("treatment-plan-list", kwargs={"pk": self.patient.id}),
            {"status": "draft", "notes": "Plan inicial"},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        plan_id = resp.data["id"]
        # Agregar ítem al plan
        resp = self.client.post(
            reverse("treatment-plan-item-create", kwargs={"pk": plan_id}),
            {"treatment": str(self.treatment.id), "tooth_fdi_code": "16",
             "order": 1, "estimated_price": "200.00"},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        plan = TreatmentPlan.objects.get(id=plan_id)
        self.assertEqual(plan.items.count(), 1)

    def test_update_treatment_plan_item_status(self):
        from apps.clinical.models import TreatmentPlanItem

        plan = TreatmentPlan.objects.create(
            tenant=self.tenant, patient=self.patient, created_by=self.doctor
        )
        item = TreatmentPlanItem.objects.create(
            treatment_plan=plan, treatment=self.treatment, order=1
        )
        self.client.force_authenticate(user=self.doctor_user)
        resp = self.client.patch(
            reverse("treatment-plan-item-update", kwargs={"pk": item.id}),
            {"status": "done"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        item.refresh_from_db()
        self.assertEqual(item.status, "done")
