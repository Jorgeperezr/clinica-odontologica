from datetime import timedelta

from django.utils import timezone
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.agenda.models import Appointment, Doctor
from apps.common.models import Tenant
from apps.patients.models import Patient


class AgendaTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Test", ruc="1234567890001")
        self.reception = User.objects.create_user(
            email="recep@test.com", password="superseguro123", role="reception", tenant=self.tenant
        )
        self.doctor_user = User.objects.create_user(
            email="doc@test.com", password="superseguro123", role="doctor", tenant=self.tenant
        )
        self.doctor = Doctor.objects.create(tenant=self.tenant, user=self.doctor_user)
        self.patient = Patient.objects.create(
            tenant=self.tenant, first_name="María", last_name="Pérez", national_id="0102030405"
        )
        self.start = timezone.now() + timedelta(days=1)
        self.end = self.start + timedelta(minutes=30)

    def _create_appointment(self, start=None, end=None):
        return Appointment.objects.create(
            tenant=self.tenant, patient=self.patient, doctor=self.doctor,
            scheduled_start=start or self.start, scheduled_end=end or self.end,
            created_by=self.reception,
        )

    def test_reception_creates_appointment(self):
        self.client.force_authenticate(user=self.reception)
        resp = self.client.post(reverse("appointment-list"), {
            "patient": str(self.patient.id), "doctor": str(self.doctor.id),
            "scheduled_start": self.start.isoformat(), "scheduled_end": self.end.isoformat(),
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_cannot_create_overlapping_appointment(self):
        self._create_appointment()
        self.client.force_authenticate(user=self.reception)
        # Cita que se solapa (empieza 10 min después, dentro de la anterior)
        resp = self.client.post(reverse("appointment-list"), {
            "patient": str(self.patient.id), "doctor": str(self.doctor.id),
            "scheduled_start": (self.start + timedelta(minutes=10)).isoformat(),
            "scheduled_end": (self.end + timedelta(minutes=10)).isoformat(),
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_create_appointment_in_past(self):
        self.client.force_authenticate(user=self.reception)
        past = timezone.now() - timedelta(days=1)
        resp = self.client.post(reverse("appointment-list"), {
            "patient": str(self.patient.id), "doctor": str(self.doctor.id),
            "scheduled_start": past.isoformat(),
            "scheduled_end": (past + timedelta(minutes=30)).isoformat(),
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_appointment(self):
        appt = self._create_appointment()
        self.client.force_authenticate(user=self.reception)
        resp = self.client.post(reverse("appointment-confirm", kwargs={"pk": appt.id}))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        appt.refresh_from_db()
        self.assertEqual(appt.status, "confirmed")

    def test_checkin_checkout_flow(self):
        appt = self._create_appointment()
        self.client.force_authenticate(user=self.reception)
        resp = self.client.post(reverse("appointment-checkin", kwargs={"pk": appt.id}))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        appt.refresh_from_db()
        self.assertIsNotNone(appt.checkin_at)

        resp = self.client.post(reverse("appointment-checkout", kwargs={"pk": appt.id}))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        appt.refresh_from_db()
        self.assertIsNotNone(appt.checkout_at)
        self.assertEqual(appt.status, "completed")

    def test_doctor_only_sees_own_agenda(self):
        # Otro doctor con su cita
        other_user = User.objects.create_user(
            email="doc2@test.com", password="superseguro123", role="doctor", tenant=self.tenant
        )
        other_doctor = Doctor.objects.create(tenant=self.tenant, user=other_user)
        self._create_appointment()  # cita del doctor 1
        Appointment.objects.create(
            tenant=self.tenant, patient=self.patient, doctor=other_doctor,
            scheduled_start=self.start + timedelta(hours=2),
            scheduled_end=self.end + timedelta(hours=2),
        )
        # El doctor 1 solo debe ver su propia cita
        self.client.force_authenticate(user=self.doctor_user)
        resp = self.client.get(reverse("appointment-list"))
        self.assertEqual(resp.data["count"], 1)

    def test_reschedule_to_conflicting_slot_rejected(self):
        self._create_appointment()  # ocupa el slot original
        appt2 = self._create_appointment(
            start=self.start + timedelta(hours=3), end=self.end + timedelta(hours=3)
        )
        self.client.force_authenticate(user=self.reception)
        # Reagendar appt2 al horario de appt1 -> conflicto
        resp = self.client.post(
            reverse("appointment-reschedule", kwargs={"pk": appt2.id}),
            {"new_start": self.start.isoformat(), "new_end": self.end.isoformat()},
        )
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_agenda_weekly_view(self):
        self._create_appointment()
        self.client.force_authenticate(user=self.reception)
        resp = self.client.get(reverse("agenda-view"), {"mode": "weekly"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
