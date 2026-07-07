from datetime import date

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.agenda.models import Doctor
from apps.common.models import Tenant
from apps.patients.models import Patient
from apps.specialties.models import Specialty, SpecialtyForm


class SpecialtyFormTests(APITestCase):
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
            tenant=self.tenant, first_name="Sofía", last_name="Vega", national_id="0505050505"
        )
        self.perio = Specialty.objects.create(tenant=self.tenant, name="Periodoncia")

    def test_form_template_returns_fields(self):
        self.client.force_authenticate(user=self.doctor_user)
        resp = self.client.get(
            reverse("specialty-form-template", kwargs={"pk": self.perio.id})
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["specialty"], "Periodoncia")
        # Periodoncia tiene 4 campos base definidos
        self.assertEqual(len(resp.data["fields"]), 4)
        keys = [f["key"] for f in resp.data["fields"]]
        self.assertIn("profundidad_bolsa", keys)

    def test_template_empty_for_unknown_specialty(self):
        custom = Specialty.objects.create(tenant=self.tenant, name="Implantología")
        self.client.force_authenticate(user=self.doctor_user)
        resp = self.client.get(
            reverse("specialty-form-template", kwargs={"pk": custom.id})
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["fields"], [])

    def test_doctor_creates_specialty_form(self):
        self.client.force_authenticate(user=self.doctor_user)
        resp = self.client.post(
            reverse("patient-specialty-forms", kwargs={"pk": self.patient.id}),
            {
                "specialty": str(self.perio.id),
                "patient": str(self.patient.id),
                "date": str(date.today()),
                "form_data": {"profundidad_bolsa": 4, "sangrado_sondaje": True},
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SpecialtyForm.objects.count(), 1)
        form = SpecialtyForm.objects.get()
        self.assertEqual(form.form_data["profundidad_bolsa"], 4)
        self.assertEqual(form.doctor, self.doctor)

    def test_reception_cannot_fill_specialty_form(self):
        self.client.force_authenticate(user=self.reception)
        resp = self.client.post(
            reverse("patient-specialty-forms", kwargs={"pk": self.patient.id}),
            {"specialty": str(self.perio.id), "patient": str(self.patient.id),
             "date": str(date.today()), "form_data": {}},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_flexible_form_data_accepts_any_fields(self):
        """El JSONField acepta cualquier estructura (flexibilidad de diseño)."""
        self.client.force_authenticate(user=self.doctor_user)
        resp = self.client.post(
            reverse("patient-specialty-forms", kwargs={"pk": self.patient.id}),
            {
                "specialty": str(self.perio.id),
                "patient": str(self.patient.id),
                "date": str(date.today()),
                "form_data": {"campo_personalizado_del_doctor": "valor libre", "otro": 123},
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        form = SpecialtyForm.objects.get()
        self.assertEqual(form.form_data["campo_personalizado_del_doctor"], "valor libre")

    def test_multiple_specialty_forms_per_patient(self):
        """Un paciente puede tener formularios de varias especialidades (RF-ESP-03)."""
        endo = Specialty.objects.create(tenant=self.tenant, name="Endodoncia")
        self.client.force_authenticate(user=self.doctor_user)
        for spec in [self.perio, endo]:
            self.client.post(
                reverse("patient-specialty-forms", kwargs={"pk": self.patient.id}),
                {"specialty": str(spec.id), "patient": str(self.patient.id),
                 "date": str(date.today()), "form_data": {}},
                format="json",
            )
        self.assertEqual(SpecialtyForm.objects.filter(patient=self.patient).count(), 2)
