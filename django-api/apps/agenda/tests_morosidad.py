"""Tests del bloqueo por morosidad (Sprint 9) — RF-AGN-07 / RN-AGN-01."""

from datetime import date, timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.agenda.models import Doctor
from apps.billing.models import Budget, Installment, PaymentPlan
from apps.common.models import Tenant
from apps.configuration.models import SystemParameter
from apps.patients.models import Patient


class MorosidadBlockTests(APITestCase):
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
            tenant=self.tenant, first_name="Deudor", last_name="Moroso", national_id="0808080808"
        )
        # Parámetro de morosidad: 30 días
        SystemParameter.objects.create(tenant=self.tenant, key="dias_morosidad", value="30")
        self.start = timezone.now() + timedelta(days=1)
        self.end = self.start + timedelta(minutes=30)

    def _make_overdue_installment(self, days_overdue=45):
        budget = Budget.objects.create(
            tenant=self.tenant, patient=self.patient, status="approved",
            total_amount=Decimal("500.00"),
        )
        plan = PaymentPlan.objects.create(
            tenant=self.tenant, budget=budget, patient=self.patient,
            total_amount=Decimal("500.00"), installment_count=1,
        )
        Installment.objects.create(
            tenant=self.tenant, payment_plan=plan, patient=self.patient,
            number=1, due_date=date.today() - timedelta(days=days_overdue),
            amount=Decimal("500.00"),
        )

    def _appointment_payload(self):
        return {
            "patient": str(self.patient.id), "doctor": str(self.doctor.id),
            "scheduled_start": self.start.isoformat(), "scheduled_end": self.end.isoformat(),
        }

    def test_delinquent_patient_blocked(self):
        self._make_overdue_installment(days_overdue=45)  # supera los 30 días
        self.client.force_authenticate(user=self.reception)
        resp = self.client.post(reverse("appointment-list"), self._appointment_payload())
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["error"]["code"], "patient_delinquent")

    def test_override_allows_appointment(self):
        self._make_overdue_installment(days_overdue=45)
        self.client.force_authenticate(user=self.reception)
        payload = self._appointment_payload()
        payload["override"] = "true"
        resp = self.client.post(reverse("appointment-list"), payload)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_recent_overdue_not_blocking(self):
        # Cuota vencida hace 10 días (< 30) no bloquea todavía
        self._make_overdue_installment(days_overdue=10)
        self.client.force_authenticate(user=self.reception)
        resp = self.client.post(reverse("appointment-list"), self._appointment_payload())
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_patient_without_debt_not_blocked(self):
        self.client.force_authenticate(user=self.reception)
        resp = self.client.post(reverse("appointment-list"), self._appointment_payload())
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_paid_installment_not_blocking(self):
        budget = Budget.objects.create(
            tenant=self.tenant, patient=self.patient, status="approved",
            total_amount=Decimal("500.00"),
        )
        plan = PaymentPlan.objects.create(
            tenant=self.tenant, budget=budget, patient=self.patient,
            total_amount=Decimal("500.00"), installment_count=1,
        )
        Installment.objects.create(
            tenant=self.tenant, payment_plan=plan, patient=self.patient,
            number=1, due_date=date.today() - timedelta(days=60),
            amount=Decimal("500.00"), status="paid",  # ya pagada
        )
        self.client.force_authenticate(user=self.reception)
        resp = self.client.post(reverse("appointment-list"), self._appointment_payload())
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)


class ReportsAndTaskTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Test", ruc="1234567890001")
        self.admin = User.objects.create_user(
            email="admin@test.com", password="superseguro123", role="admin", tenant=self.tenant
        )
        self.patient = Patient.objects.create(
            tenant=self.tenant, first_name="Ana", last_name="Paz", national_id="1010101010"
        )

    def test_mark_overdue_task(self):
        from apps.billing.models import Budget, Installment, PaymentPlan
        from apps.billing.tasks import mark_overdue_installments

        budget = Budget.objects.create(
            tenant=self.tenant, patient=self.patient, status="approved",
            total_amount=Decimal("100.00"),
        )
        plan = PaymentPlan.objects.create(
            tenant=self.tenant, budget=budget, patient=self.patient,
            total_amount=Decimal("100.00"), installment_count=1,
        )
        Installment.objects.create(
            tenant=self.tenant, payment_plan=plan, patient=self.patient,
            number=1, due_date=date.today() - timedelta(days=5),
            amount=Decimal("100.00"), status="pending",
        )
        result = mark_overdue_installments()
        self.assertEqual(result["marked_overdue"], 1)
        inst = Installment.objects.get()
        self.assertEqual(inst.status, "overdue")

    def test_delinquency_report(self):
        from apps.billing.models import Budget, Installment, PaymentPlan

        SystemParameter = __import__(
            "apps.configuration.models", fromlist=["SystemParameter"]
        ).SystemParameter
        SystemParameter.objects.create(tenant=self.tenant, key="dias_morosidad", value="30")

        budget = Budget.objects.create(
            tenant=self.tenant, patient=self.patient, status="approved",
            total_amount=Decimal("200.00"),
        )
        plan = PaymentPlan.objects.create(
            tenant=self.tenant, budget=budget, patient=self.patient,
            total_amount=Decimal("200.00"), installment_count=1,
        )
        Installment.objects.create(
            tenant=self.tenant, payment_plan=plan, patient=self.patient,
            number=1, due_date=date.today() - timedelta(days=40), amount=Decimal("200.00"),
        )
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(reverse("report-delinquency"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["patients"]), 1)
        self.assertTrue(resp.data["patients"][0]["is_blocking"])

    def test_financial_report(self):
        from apps.billing.models import Payment

        Payment.objects.create(
            tenant=self.tenant, patient=self.patient, amount=Decimal("150.00"),
            method="cash", date=date.today(),
        )
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(reverse("report-financial"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["total_income"], "150.00")
