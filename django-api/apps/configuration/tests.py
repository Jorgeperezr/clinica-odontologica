from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.common.models import Tenant
from apps.configuration.models import SystemParameter, Treatment
from apps.specialties.models import Specialty


class ConfigurationTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Test", ruc="1234567890001")
        self.admin = User.objects.create_user(
            email="admin@test.com", password="superseguro123", role="admin", tenant=self.tenant
        )
        self.reception = User.objects.create_user(
            email="recep@test.com", password="superseguro123", role="reception", tenant=self.tenant
        )
        self.specialty = Specialty.objects.create(tenant=self.tenant, name="Ortodoncia")

    def test_admin_creates_specialty(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(reverse("specialty-list"), {"name": "Endodoncia"})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_reception_cannot_create_specialty(self):
        self.client.force_authenticate(user=self.reception)
        resp = self.client.post(reverse("specialty-list"), {"name": "Endodoncia"})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_reception_can_view_specialties(self):
        self.client.force_authenticate(user=self.reception)
        resp = self.client.get(reverse("specialty-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_duplicate_specialty_rejected(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(reverse("specialty-list"), {"name": "Ortodoncia"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_creates_treatment(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            reverse("treatment-list"),
            {"name": "Bracket metálico", "specialty": str(self.specialty.id), "base_price": "500.00"},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Treatment.objects.count(), 1)

    def test_treatment_rejects_specialty_from_other_tenant(self):
        other_tenant = Tenant.objects.create(name="Otra Clínica")
        other_specialty = Specialty.objects.create(tenant=other_tenant, name="Periodoncia")
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            reverse("treatment-list"),
            {"name": "X", "specialty": str(other_specialty.id), "base_price": "100.00"},
        )
        # No debe permitir usar una especialidad de otro tenant
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_system_parameter_value_editable(self):
        param = SystemParameter.objects.create(
            tenant=self.tenant, key="dias_morosidad", value="30"
        )
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(
            reverse("parameter-detail", kwargs={"pk": param.id}), {"value": "45"}
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        param.refresh_from_db()
        self.assertEqual(param.value, "45")


class BootstrapTests(APITestCase):
    def test_bootstrap_seeds_specialties_and_parameters(self):
        from django.core.management import call_command

        call_command("bootstrap", tenant_name="Clínica Seed")
        tenant = Tenant.objects.get(name="Clínica Seed")
        self.assertEqual(Specialty.objects.filter(tenant=tenant).count(), 5)
        self.assertEqual(
            SystemParameter.objects.filter(tenant=tenant).count(),
            len(SystemParameter.DEFAULTS),
        )

    def test_bootstrap_is_idempotent(self):
        from django.core.management import call_command

        call_command("bootstrap", tenant_name="Clínica Seed")
        call_command("bootstrap", tenant_name="Clínica Seed")
        tenant = Tenant.objects.get(name="Clínica Seed")
        # No debe duplicar especialidades al correr dos veces
        self.assertEqual(Specialty.objects.filter(tenant=tenant).count(), 5)
