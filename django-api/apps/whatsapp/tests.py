"""Tests del módulo WhatsApp (Sprint 10). Todo en modo simulado (sin Meta real)."""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.agenda.models import Appointment, Doctor
from apps.common.models import Tenant
from apps.patients.models import Patient
from apps.whatsapp.models import WhatsAppOptIn


class OptInTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Test", ruc="1234567890001")
        self.reception = User.objects.create_user(
            email="recep@test.com", password="superseguro123", role="reception", tenant=self.tenant
        )
        self.patient = Patient.objects.create(
            tenant=self.tenant, first_name="Rosa", last_name="Díaz",
            national_id="1212121212", phone="+593999888777",
        )

    def test_register_optin(self):
        self.client.force_authenticate(user=self.reception)
        resp = self.client.post(
            reverse("whatsapp-optin-list", kwargs={"pk": self.patient.id}),
            {"patient": str(self.patient.id), "channel": "registro_recepcion"},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(resp.data["is_active"])

    def test_revoke_optin(self):
        optin = WhatsAppOptIn.objects.create(tenant=self.tenant, patient=self.patient)
        self.client.force_authenticate(user=self.reception)
        resp = self.client.post(reverse("whatsapp-optin-revoke", kwargs={"pk": optin.id}))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        optin.refresh_from_db()
        self.assertIsNotNone(optin.revoked_at)
        self.assertFalse(optin.is_active)


class ReminderTaskTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Test", ruc="1234567890001")
        from apps.configuration.models import SystemParameter
        SystemParameter.objects.create(
            tenant=self.tenant, key="ventana_recordatorio_horas", value="24"
        )
        self.doctor_user = User.objects.create_user(
            email="doc@test.com", password="superseguro123", role="doctor", tenant=self.tenant
        )
        self.doctor = Doctor.objects.create(tenant=self.tenant, user=self.doctor_user)
        self.patient = Patient.objects.create(
            tenant=self.tenant, first_name="Juan", last_name="Soto",
            national_id="1313131313", phone="+593999111222",
        )

    def test_reminder_only_with_optin(self):
        """El recordatorio solo se envía si el paciente tiene opt-in activo."""
        from apps.whatsapp.tasks import send_appointment_reminders

        # Cita dentro de la ventana, pero SIN opt-in
        Appointment.objects.create(
            tenant=self.tenant, patient=self.patient, doctor=self.doctor,
            scheduled_start=timezone.now() + timedelta(hours=12),
            scheduled_end=timezone.now() + timedelta(hours=12, minutes=30),
            status="confirmed",
        )
        result = send_appointment_reminders()
        self.assertEqual(result["reminders_sent"], 0)  # sin opt-in, no envía

        # Ahora con opt-in
        WhatsAppOptIn.objects.create(tenant=self.tenant, patient=self.patient)
        result = send_appointment_reminders()
        self.assertEqual(result["reminders_sent"], 1)

    def test_reminder_respects_window(self):
        """Citas fuera de la ventana de recordatorio no reciben mensaje."""
        from apps.whatsapp.tasks import send_appointment_reminders

        WhatsAppOptIn.objects.create(tenant=self.tenant, patient=self.patient)
        # Cita en 3 días (fuera de la ventana de 24h)
        Appointment.objects.create(
            tenant=self.tenant, patient=self.patient, doctor=self.doctor,
            scheduled_start=timezone.now() + timedelta(days=3),
            scheduled_end=timezone.now() + timedelta(days=3, minutes=30),
            status="confirmed",
        )
        result = send_appointment_reminders()
        self.assertEqual(result["reminders_sent"], 0)


class WebhookEventTests(APITestCase):
    """Tests del endpoint interno que recibe eventos del gateway."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Test", ruc="1234567890001")
        self.doctor_user = User.objects.create_user(
            email="doc@test.com", password="superseguro123", role="doctor", tenant=self.tenant
        )
        self.doctor = Doctor.objects.create(tenant=self.tenant, user=self.doctor_user)
        self.patient = Patient.objects.create(
            tenant=self.tenant, first_name="Pedro", last_name="Luna", national_id="1414141414"
        )
        self.appt = Appointment.objects.create(
            tenant=self.tenant, patient=self.patient, doctor=self.doctor,
            scheduled_start=timezone.now() + timedelta(days=1),
            scheduled_end=timezone.now() + timedelta(days=1, minutes=30),
            status="pending",
        )

    def test_inbound_confirmation_confirms_appointment(self):
        from django.conf import settings

        resp = self.client.post(
            "/internal/whatsapp/events/",
            {
                "event_type": "inbound_message",
                "text": "confirmo",
                "appointment_id": str(self.appt.id),
            },
            format="json",
            HTTP_X_SERVICE_TOKEN=settings.INTERNAL_SERVICE_TOKEN,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.appt.refresh_from_db()
        self.assertEqual(self.appt.status, "confirmed")

    def test_internal_endpoint_rejects_without_token(self):
        resp = self.client.post(
            "/internal/whatsapp/events/",
            {"event_type": "message_status"},
            format="json",
        )
        # 401 (no autenticado) o 403 (prohibido) — ambos rechazan el acceso.
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
