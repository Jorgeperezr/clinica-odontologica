from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import OTPCode, User
from apps.common.models import Tenant


class AuthTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Test", ruc="1234567890001")
        self.admin = User.objects.create_user(
            email="admin@test.com", password="superseguro123", role="admin", tenant=self.tenant
        )

    def test_staff_login_ok(self):
        resp = self.client.post(
            reverse("staff-login"),
            {"email": "admin@test.com", "password": "superseguro123"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)
        self.assertEqual(resp.data["role"], "admin")

    def test_patient_cannot_use_staff_login(self):
        User.objects.create_user(phone="+593999999999", role="patient", tenant=self.tenant)
        resp = self.client.post(
            reverse("staff-login"), {"email": "", "password": ""}
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_otp_request_creates_code(self):
        resp = self.client.post(reverse("otp-request"), {"phone": "+593988888888"})
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        user = User.objects.get(phone="+593988888888")
        self.assertEqual(user.role, "patient")
        self.assertTrue(OTPCode.objects.filter(user=user).exists())

    def test_only_admin_lists_users(self):
        reception = User.objects.create_user(
            email="recep@test.com", password="superseguro123", role="reception", tenant=self.tenant
        )
        self.client.force_authenticate(user=reception)
        resp = self.client.get(reverse("user-list"))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(reverse("user-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class MeEndpointTests(APITestCase):
    def test_me_returns_profile(self):
        from apps.common.models import Tenant
        tenant = Tenant.objects.create(name="T me")
        user = User.objects.create_user(
            email="me@test.com", password="superseguro123",
            role="reception", tenant=tenant, full_name="Laura Vera",
        )
        self.client.force_authenticate(user=user)
        resp = self.client.get("/api/v1/auth/me/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["role"], "reception")
        self.assertEqual(resp.data["full_name"], "Laura Vera")

    def test_me_requires_auth(self):
        resp = self.client.get("/api/v1/auth/me/")
        self.assertIn(resp.status_code, [401, 403])
