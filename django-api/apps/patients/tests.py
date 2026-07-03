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
