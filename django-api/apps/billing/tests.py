from datetime import date, timedelta
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.agenda.models import Doctor
from apps.billing.models import Budget, Installment, PaymentPlan
from apps.common.models import Tenant
from apps.configuration.models import Treatment
from apps.patients.models import Patient
from apps.specialties.models import Specialty


class BillingTests(APITestCase):
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
            tenant=self.tenant, first_name="Carlos", last_name="Ruiz", national_id="0707070707"
        )
        self.specialty = Specialty.objects.create(tenant=self.tenant, name="Ortodoncia")
        self.treatment = Treatment.objects.create(
            tenant=self.tenant, name="Brackets", specialty=self.specialty, base_price="1000.00"
        )

    def _create_budget_with_item(self, unit_price="1000.00", quantity=1):
        budget = Budget.objects.create(tenant=self.tenant, patient=self.patient)
        from apps.billing.models import BudgetItem
        BudgetItem.objects.create(
            budget=budget, treatment=self.treatment,
            quantity=quantity, unit_price=Decimal(unit_price),
        )
        budget.recalculate_total()
        return budget

    def test_create_budget(self):
        self.client.force_authenticate(user=self.reception)
        resp = self.client.post(
            reverse("budget-list", kwargs={"pk": self.patient.id}),
            {"patient": str(self.patient.id), "notes": "Presupuesto ortodoncia"},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_budget_total_recalculates_with_items(self):
        budget = self._create_budget_with_item(unit_price="500.00", quantity=2)
        self.assertEqual(budget.total_amount, Decimal("1000.00"))

    def test_generate_payment_plan_divides_evenly(self):
        budget = self._create_budget_with_item(unit_price="1200.00")
        budget.status = Budget.Status.APPROVED
        budget.save()
        self.client.force_authenticate(user=self.reception)
        resp = self.client.post(
            reverse("generate-payment-plan", kwargs={"pk": budget.id}),
            {"installment_count": 3, "first_due_date": str(date.today())},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        plan = PaymentPlan.objects.get(budget=budget)
        self.assertEqual(plan.installments.count(), 3)
        # La suma de las cuotas debe ser exactamente el total (sin centavos perdidos)
        total_cuotas = sum(i.amount for i in plan.installments.all())
        self.assertEqual(total_cuotas, Decimal("1200.00"))

    def test_payment_plan_last_installment_absorbs_rounding(self):
        # 1000 / 3 = 333.33, 333.33, 333.34 (la última ajusta)
        budget = self._create_budget_with_item(unit_price="1000.00")
        budget.status = Budget.Status.APPROVED
        budget.save()
        self.client.force_authenticate(user=self.reception)
        self.client.post(
            reverse("generate-payment-plan", kwargs={"pk": budget.id}),
            {"installment_count": 3, "first_due_date": str(date.today())},
        )
        plan = PaymentPlan.objects.get(budget=budget)
        amounts = sorted(i.amount for i in plan.installments.all())
        self.assertEqual(amounts, [Decimal("333.33"), Decimal("333.33"), Decimal("333.34")])

    def test_cannot_generate_plan_for_unapproved_budget(self):
        budget = self._create_budget_with_item()
        self.client.force_authenticate(user=self.reception)
        resp = self.client.post(
            reverse("generate-payment-plan", kwargs={"pk": budget.id}),
            {"installment_count": 3, "first_due_date": str(date.today())},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pay_installment_marks_paid_when_settled(self):
        budget = self._create_budget_with_item(unit_price="300.00")
        budget.status = Budget.Status.APPROVED
        budget.save()
        self.client.force_authenticate(user=self.reception)
        self.client.post(
            reverse("generate-payment-plan", kwargs={"pk": budget.id}),
            {"installment_count": 1, "first_due_date": str(date.today())},
        )
        installment = Installment.objects.get()
        resp = self.client.post(
            reverse("installment-pay", kwargs={"pk": installment.id}),
            {"amount": "300.00", "method": "cash"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        installment.refresh_from_db()
        self.assertEqual(installment.status, "paid")

    def test_partial_payment_keeps_installment_pending(self):
        budget = self._create_budget_with_item(unit_price="300.00")
        budget.status = Budget.Status.APPROVED
        budget.save()
        self.client.force_authenticate(user=self.reception)
        self.client.post(
            reverse("generate-payment-plan", kwargs={"pk": budget.id}),
            {"installment_count": 1, "first_due_date": str(date.today())},
        )
        installment = Installment.objects.get()
        # Pago parcial (100 de 300)
        self.client.post(
            reverse("installment-pay", kwargs={"pk": installment.id}),
            {"amount": "100.00", "method": "cash"},
        )
        installment.refresh_from_db()
        self.assertEqual(installment.status, "pending")
        self.assertEqual(installment.balance, Decimal("200.00"))

    def test_account_statement(self):
        budget = self._create_budget_with_item(unit_price="600.00")
        budget.status = Budget.Status.APPROVED
        budget.save()
        self.client.force_authenticate(user=self.reception)
        self.client.post(
            reverse("generate-payment-plan", kwargs={"pk": budget.id}),
            {"installment_count": 2, "first_due_date": str(date.today())},
        )
        resp = self.client.get(
            reverse("account-statement", kwargs={"pk": self.patient.id})
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["total_amount"], "600.00")
        self.assertEqual(resp.data["balance"], "600.00")

    def test_overdue_detection_in_statement(self):
        budget = self._create_budget_with_item(unit_price="600.00")
        budget.status = Budget.Status.APPROVED
        budget.save()
        # Plan con primera cuota vencida (ayer)
        plan = PaymentPlan.objects.create(
            tenant=self.tenant, budget=budget, patient=self.patient,
            total_amount=Decimal("600.00"), installment_count=1,
        )
        Installment.objects.create(
            tenant=self.tenant, payment_plan=plan, patient=self.patient,
            number=1, due_date=date.today() - timedelta(days=1), amount=Decimal("600.00"),
        )
        self.client.force_authenticate(user=self.reception)
        resp = self.client.get(
            reverse("account-statement", kwargs={"pk": self.patient.id})
        )
        self.assertEqual(resp.data["overdue_count"], 1)
