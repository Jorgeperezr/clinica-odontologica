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


class OdontogramTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Test", ruc="1234567890001")
        self.doctor_user = User.objects.create_user(
            email="doc@test.com", password="superseguro123", role="doctor", tenant=self.tenant
        )
        self.doctor = Doctor.objects.create(tenant=self.tenant, user=self.doctor_user)
        self.patient = Patient.objects.create(
            tenant=self.tenant, first_name="Ana", last_name="López", national_id="0909090909"
        )
        # Sembrar estados del odontograma vía bootstrap
        from django.core.management import call_command
        call_command("bootstrap", tenant_name=self.tenant.name)

    def _get_state(self, code):
        from apps.clinical.models import OdontogramState
        return OdontogramState.objects.get(tenant=self.tenant, code=code)

    def test_odontogram_states_seeded(self):
        from apps.clinical.models import OdontogramState
        self.assertEqual(OdontogramState.objects.filter(tenant=self.tenant).count(), 12)

    def test_list_odontogram_states(self):
        self.client.force_authenticate(user=self.doctor_user)
        resp = self.client.get(reverse("odontogram-state-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 12)

    def test_create_tooth_record(self):
        self.client.force_authenticate(user=self.doctor_user)
        state = self._get_state("CARIES")
        resp = self.client.post(
            reverse("tooth-record-list", kwargs={"pk": self.patient.id}),
            {"tooth_fdi_code": "16", "surface": "occlusal",
             "state": str(state.id), "date": "2026-07-06"},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["state_code"], "CARIES")

    def test_tooth_record_history_not_overwritten(self):
        """Cada registro crea una fila nueva, nunca actualiza (trazabilidad)."""
        from apps.clinical.models import ToothRecord
        self.client.force_authenticate(user=self.doctor_user)
        caries = self._get_state("CARIES")
        obturado = self._get_state("OBTURADO")
        # Registrar caries en la pieza 16
        self.client.post(
            reverse("tooth-record-list", kwargs={"pk": self.patient.id}),
            {"tooth_fdi_code": "16", "surface": "occlusal",
             "state": str(caries.id), "date": "2026-01-01"},
        )
        # Luego registrar obturado (no borra el anterior)
        self.client.post(
            reverse("tooth-record-list", kwargs={"pk": self.patient.id}),
            {"tooth_fdi_code": "16", "surface": "occlusal",
             "state": str(obturado.id), "date": "2026-03-15"},
        )
        self.assertEqual(ToothRecord.objects.filter(patient=self.patient).count(), 2)

    def test_current_odontogram_returns_latest(self):
        """La vista current/ devuelve el estado más reciente por pieza/superficie."""
        self.client.force_authenticate(user=self.doctor_user)
        caries = self._get_state("CARIES")
        obturado = self._get_state("OBTURADO")
        self.client.post(
            reverse("tooth-record-list", kwargs={"pk": self.patient.id}),
            {"tooth_fdi_code": "16", "surface": "occlusal",
             "state": str(caries.id), "date": "2026-01-01"},
        )
        self.client.post(
            reverse("tooth-record-list", kwargs={"pk": self.patient.id}),
            {"tooth_fdi_code": "16", "surface": "occlusal",
             "state": str(obturado.id), "date": "2026-03-15"},
        )
        resp = self.client.get(
            reverse("odontogram-current", kwargs={"pk": self.patient.id})
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        teeth = resp.data["teeth"]
        self.assertEqual(len(teeth), 1)  # Solo 1 pieza/superficie
        self.assertEqual(teeth[0]["state_code"], "OBTURADO")  # La más reciente

    def test_tooth_record_access_is_audited(self):
        from apps.accounts.models import AuditLog
        self.client.force_authenticate(user=self.doctor_user)
        self.client.get(
            reverse("odontogram-current", kwargs={"pk": self.patient.id})
        )
        self.assertTrue(
            AuditLog.objects.filter(entity_type="Odontogram").exists()
        )


class ConsentAndExportTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Test", ruc="1234567890001")
        self.doctor_user = User.objects.create_user(
            email="doc@test.com", password="superseguro123", role="doctor", tenant=self.tenant
        )
        self.doctor = Doctor.objects.create(tenant=self.tenant, user=self.doctor_user)
        self.patient = Patient.objects.create(
            tenant=self.tenant, first_name="Luis", last_name="Mora", national_id="1111111111"
        )

    def test_create_consent(self):
        self.client.force_authenticate(user=self.doctor_user)
        resp = self.client.post(
            reverse("consent-list", kwargs={"pk": self.patient.id}),
            {"title": "Consentimiento para extracción",
             "body_text": "Autorizo el procedimiento de extracción dental."},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertFalse(resp.data["is_signed"])

    def test_sign_consent_generates_pdf(self):
        from apps.clinical.models import InformedConsent

        consent = InformedConsent.objects.create(
            tenant=self.tenant, patient=self.patient,
            title="Consentimiento", body_text="Autorizo el tratamiento.",
        )
        self.client.force_authenticate(user=self.doctor_user)
        # PNG mínimo válido (1x1 transparente) en base64
        tiny_png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAAGElEQVR4nGNkYGD4z0AEYCJG0ahC6ikEAKYXARPmwrp4AAAAAElFTkSuQmCC"
        resp = self.client.post(
            reverse("consent-sign", kwargs={"pk": consent.id}),
            {"signature_image_base64": tiny_png},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["is_signed"])
        consent.refresh_from_db()
        self.assertIsNotNone(consent.signed_at)
        self.assertIsNotNone(consent.ip_address)
        self.assertTrue(consent.pdf_file.name.endswith(".pdf"))

    def test_export_clinical_history_pdf(self):
        from datetime import date

        from apps.clinical.models import Evolution
        Evolution.objects.create(
            tenant=self.tenant, patient=self.patient, doctor=self.doctor,
            type="clinical_note", date=date.today(), notes="Primera consulta.",
        )
        self.client.force_authenticate(user=self.doctor_user)
        resp = self.client.get(
            reverse("clinical-history-export", kwargs={"pk": self.patient.id})
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        # El contenido debe empezar con la firma de un PDF
        self.assertTrue(resp.content.startswith(b"%PDF"))

    def test_invalid_signature_rejected(self):
        from apps.clinical.models import InformedConsent

        consent = InformedConsent.objects.create(
            tenant=self.tenant, patient=self.patient,
            title="C", body_text="texto",
        )
        self.client.force_authenticate(user=self.doctor_user)
        resp = self.client.post(
            reverse("consent-sign", kwargs={"pk": consent.id}),
            {"signature_image_base64": "no-es-base64-valido!!!"},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class ClinicalWithoutDoctorProfileTests(APITestCase):
    """Admin/auxiliar (roles clínicos) sin perfil de Doctor pueden registrar."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Test", ruc="1234567890001")
        self.admin = User.objects.create_user(
            email="admin@test.com", password="superseguro123", role="admin", tenant=self.tenant
        )
        self.patient = Patient.objects.create(
            tenant=self.tenant, first_name="Eva", last_name="Cruz", national_id="1717171717"
        )

    def test_admin_without_doctor_profile_creates_evolution(self):
        from datetime import date
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            reverse("evolution-list", kwargs={"pk": self.patient.id}),
            {"type": "clinical_note", "date": str(date.today()), "notes": "Nota del admin."},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(resp.data["doctor"])

    def test_admin_without_doctor_profile_creates_tooth_record(self):
        from django.core.management import call_command
        call_command("bootstrap", tenant_name=self.tenant.name)
        from apps.clinical.models import OdontogramState
        state = OdontogramState.objects.filter(tenant=self.tenant, code="CARIES").first()
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            reverse("tooth-record-list", kwargs={"pk": self.patient.id}),
            {"tooth_fdi_code": "16", "surface": "whole",
             "state": str(state.id), "date": "2026-07-08"},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_delete_tooth_record_is_audited(self):
        """Corrección de un registro erróneo: se elimina y queda auditado."""
        from django.core.management import call_command
        call_command("bootstrap", tenant_name=self.tenant.name)
        from apps.accounts.models import AuditLog
        from apps.clinical.models import OdontogramState, ToothRecord

        state = OdontogramState.objects.filter(tenant=self.tenant, code="CARIES").first()
        record = ToothRecord.objects.create(
            tenant=self.tenant, patient=self.patient,
            tooth_fdi_code="16", surface="whole", state=state, date="2026-07-08",
        )
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(
            reverse("tooth-record-delete", kwargs={"pk": record.id})
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ToothRecord.objects.filter(id=record.id).exists())
        self.assertTrue(
            AuditLog.objects.filter(action="delete_tooth_record").exists()
        )
