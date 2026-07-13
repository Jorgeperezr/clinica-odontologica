from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.common.models import Tenant
from apps.patients.models import Patient


class PatientTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Test", ruc="1234567890001")
        self.reception = User.objects.create_user(
            email="recep@test.com", password="superseguro123", role="reception", tenant=self.tenant
        )
        self.doctor = User.objects.create_user(
            email="doc@test.com", password="superseguro123", role="doctor", tenant=self.tenant
        )

    def test_reception_creates_patient(self):
        self.client.force_authenticate(user=self.reception)
        resp = self.client.post(
            reverse("patient-list"),
            {"first_name": "María", "last_name": "Pérez", "national_id": "0102030405"},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Patient.objects.count(), 1)

    def test_duplicate_national_id_rejected(self):
        self.client.force_authenticate(user=self.reception)
        payload = {"first_name": "A", "last_name": "B", "national_id": "0102030405"}
        self.client.post(reverse("patient-list"), payload)
        resp = self.client.post(reverse("patient-list"), payload)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_doctor_cannot_create_patient(self):
        self.client.force_authenticate(user=self.doctor)
        resp = self.client.post(
            reverse("patient-list"),
            {"first_name": "X", "last_name": "Y", "national_id": "0999999999"},
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_search_by_national_id(self):
        Patient.objects.create(
            tenant=self.tenant, first_name="Juan", last_name="Gómez", national_id="1717171717"
        )
        self.client.force_authenticate(user=self.reception)
        resp = self.client.get(reverse("patient-list"), {"search": "1717"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)

    def test_reception_cannot_access_medical_background(self):
        patient = Patient.objects.create(
            tenant=self.tenant, first_name="Ana", last_name="Ruiz", national_id="1818181818"
        )
        self.client.force_authenticate(user=self.reception)
        resp = self.client.get(
            reverse("patient-medical-background", kwargs={"pk": patient.id})
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_accesses_medical_background(self):
        patient = Patient.objects.create(
            tenant=self.tenant, first_name="Ana", last_name="Ruiz", national_id="1818181818"
        )
        self.client.force_authenticate(user=self.doctor)
        resp = self.client.get(
            reverse("patient-medical-background", kwargs={"pk": patient.id})
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class PatientOrderingTests(APITestCase):
    """Ordenamientos del listado de pacientes (mejora de usabilidad)."""

    def setUp(self):
        from apps.common.models import Tenant
        self.tenant = Tenant.objects.create(name="T orden")
        self.user = User.objects.create_user(
            email="u@orden.ec", password="superseguro123", role="admin", tenant=self.tenant,
        )
        self.client.force_authenticate(user=self.user)
        # Tres pacientes con apellidos distintos
        self.p_ana = Patient.objects.create(
            tenant=self.tenant, first_name="Ana", last_name="Alvarez", national_id="1111111111",
        )
        self.p_zoe = Patient.objects.create(
            tenant=self.tenant, first_name="Zoe", last_name="Zambrano", national_id="2222222222",
        )
        self.p_leo = Patient.objects.create(
            tenant=self.tenant, first_name="Leo", last_name="Lopez", national_id="3333333333",
        )

    def _names(self, ordering):
        resp = self.client.get(f"/api/v1/patients/?ordering={ordering}")
        self.assertEqual(resp.status_code, 200, resp.content)
        results = resp.data.get("results", resp.data)
        return [r["full_name"] for r in results]

    def test_name_asc_and_desc(self):
        asc = self._names("name_asc")
        self.assertLess(asc.index("Ana Alvarez"), asc.index("Zoe Zambrano"))
        desc = self._names("name_desc")
        self.assertLess(desc.index("Zoe Zambrano"), desc.index("Ana Alvarez"))

    def test_created_desc_puts_newest_first(self):
        # El último creado (Leo) debe ir primero en created_desc
        names = self._names("created_desc")
        self.assertEqual(names[0], "Leo Lopez")

    def test_attention_and_next_appt_do_not_break(self):
        # Solo verificamos que responden 200 y traen los campos anotados
        resp = self.client.get("/api/v1/patients/?ordering=attention_desc")
        self.assertEqual(resp.status_code, 200)
        results = resp.data.get("results", resp.data)
        self.assertIn("attention_count", results[0])
        self.assertIn("next_appointment", results[0])
        resp = self.client.get("/api/v1/patients/?ordering=next_appt_asc")
        self.assertEqual(resp.status_code, 200)

    def test_invalid_ordering_falls_back(self):
        # Un ordering inválido no rompe: cae a name_asc
        resp = self.client.get("/api/v1/patients/?ordering=xxx")
        self.assertEqual(resp.status_code, 200)
