"""
Tests del panel de plataforma (Sprint 21, según especificación):
dashboard, gestión de clínicas, administradores, auditoría, configuración
— y los dos principios clave: aislamiento entre clínicas y NO acceso del
Super Administrador a información operativa.
"""

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.common.models import PlatformConfiguration, Tenant


class PlatformBase(APITestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            email="sa@plataforma.ec", password="superseguro123",
            role="superadmin", tenant=None, full_name="Super Admin",
        )
        self.client.force_authenticate(user=self.superadmin)


class DashboardTests(PlatformBase):
    def test_overview_per_spec(self):
        Tenant.objects.create(name="C1")
        t2 = Tenant.objects.create(name="C2", is_active=False)
        User.objects.create_user(email="a1@c.ec", password="superseguro123", role="admin",
                                 tenant=t2)
        resp = self.client.get("/api/v1/platform/overview/")
        self.assertEqual(resp.data["clinics_total"], 2)
        self.assertEqual(resp.data["clinics_active"], 1)
        self.assertEqual(resp.data["clinics_suspended"], 1)
        self.assertEqual(resp.data["clinic_admins_total"], 1)
        # NO expone datos operativos (pacientes, ingresos, etc.)
        self.assertNotIn("patients_total", resp.data)


class ClinicManagementTests(PlatformBase):
    def test_list_clinics_regression(self):
        """Regresión del bug del GET (FieldError por Count('patients'))."""
        Tenant.objects.create(name="Clínica Lista")
        resp = self.client.get("/api/v1/platform/clinics/")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(resp.data), 1)

    def test_create_clinic_seeds_catalog(self):
        resp = self.client.post("/api/v1/platform/clinics/", {
            "name": "Clínica Norte", "ruc": "1111111111001",
            "address": "Av. Siempre Viva 123", "phone": "+59372570000",
            "email": "contacto@norte.ec",
        })
        self.assertEqual(resp.status_code, 201, resp.content)
        tenant = Tenant.objects.get(name="Clínica Norte")
        self.assertEqual(tenant.address, "Av. Siempre Viva 123")
        from apps.clinical.models import OdontogramState
        self.assertEqual(OdontogramState.objects.filter(tenant=tenant).count(), 22)

    def test_edit_clinic_general_info(self):
        tenant = Tenant.objects.create(name="Clínica Editar")
        resp = self.client.patch(f"/api/v1/platform/clinics/{tenant.id}/", {
            "phone": "+59399999", "email": "nuevo@editar.ec",
        })
        self.assertEqual(resp.status_code, 200, resp.content)
        tenant.refresh_from_db()
        self.assertEqual(tenant.email, "nuevo@editar.ec")

    def test_suspend_clinic_blocks_users(self):
        from rest_framework_simplejwt.tokens import RefreshToken
        tenant = Tenant.objects.create(name="Clínica Susp")
        user = User.objects.create_user(
            email="staff@susp.ec", password="superseguro123", role="admin", tenant=tenant,
        )
        token = str(RefreshToken.for_user(user).access_token)

        self.client.patch(f"/api/v1/platform/clinics/{tenant.id}/", {"is_active": False})

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        resp = self.client.get("/api/v1/patients/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class ClinicAdminTests(PlatformBase):
    def setUp(self):
        super().setUp()
        self.tenant = Tenant.objects.create(name="Clínica AdminTests")

    def _create_admin(self):
        return self.client.post(f"/api/v1/platform/clinics/{self.tenant.id}/admin/", {
            "email": "admin@ct.ec", "full_name": "Ana Ct", "password": "ClaveSegura26",
        })

    def test_create_and_get_principal_admin(self):
        resp = self._create_admin()
        self.assertEqual(resp.status_code, 201, resp.content)
        resp = self.client.get(f"/api/v1/platform/clinics/{self.tenant.id}/admin/")
        self.assertEqual(resp.data["admin"]["email"], "admin@ct.ec")

    def test_update_admin_email_and_toggle(self):
        self._create_admin()
        resp = self.client.patch(f"/api/v1/platform/clinics/{self.tenant.id}/admin/", {
            "email": "nuevo@ct.ec", "is_active": False,
        })
        self.assertEqual(resp.status_code, 200, resp.content)
        admin = User.objects.get(full_name="Ana Ct")
        self.assertEqual(admin.email, "nuevo@ct.ec")
        self.assertFalse(admin.is_active)

    def test_reset_password_returns_temp_once(self):
        self._create_admin()
        resp = self.client.post(f"/api/v1/platform/clinics/{self.tenant.id}/admin/reset-password/")
        self.assertEqual(resp.status_code, 200, resp.content)
        temp = resp.data["temporary_password"]
        admin = User.objects.get(email="admin@ct.ec")
        self.assertTrue(admin.check_password(temp))
        self.assertFalse(admin.check_password("ClaveSegura26"))


class IsolationAndPrivacyTests(PlatformBase):
    def test_data_isolation_between_clinics(self):
        from apps.patients.models import Patient
        clinic_a = Tenant.objects.create(name="Clínica A")
        clinic_b = Tenant.objects.create(name="Clínica B")
        admin_a = User.objects.create_user(email="a@a.ec", password="superseguro123",
                                           role="admin", tenant=clinic_a)
        admin_b = User.objects.create_user(email="b@b.ec", password="superseguro123",
                                           role="admin", tenant=clinic_b)
        patient_a = Patient.objects.create(
            tenant=clinic_a, first_name="Paciente", last_name="DeA", national_id="0101010101",
        )
        self.client.force_authenticate(user=admin_b)
        resp = self.client.get("/api/v1/patients/")
        results = resp.data.get("results", resp.data)
        self.assertEqual(len(results), 0)
        resp = self.client.get(f"/api/v1/patients/{patient_a.id}/")
        self.assertEqual(resp.status_code, 404)
        self.client.force_authenticate(user=admin_a)
        resp = self.client.get("/api/v1/patients/")
        self.assertEqual(len(resp.data.get("results", resp.data)), 1)

    def test_superadmin_cannot_access_operational_data(self):
        """El SA administra la plataforma; los datos clínicos le son ajenos."""
        for url in ["/api/v1/patients/", "/api/v1/appointments/",
                    "/api/v1/reports/financial/", "/api/v1/products/"]:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 403, f"{url} → {resp.status_code}")

    def test_clinic_admin_cannot_access_platform(self):
        tenant = Tenant.objects.create(name="Clínica X")
        clinic_admin = User.objects.create_user(
            email="admin@x.ec", password="superseguro123", role="admin", tenant=tenant,
        )
        self.client.force_authenticate(user=clinic_admin)
        for url in ["/api/v1/platform/clinics/", "/api/v1/platform/overview/",
                    "/api/v1/platform/audit/", "/api/v1/platform/config/"]:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 403, url)


class AuditTests(PlatformBase):
    def test_audit_records_platform_actions(self):
        self.client.post("/api/v1/platform/clinics/", {"name": "Clínica Audit"})
        tenant = Tenant.objects.get(name="Clínica Audit")
        self.client.patch(f"/api/v1/platform/clinics/{tenant.id}/", {"is_active": False})

        resp = self.client.get("/api/v1/platform/audit/")
        actions = [r["action"] for r in resp.data["results"]]
        self.assertIn("create_clinic", actions)
        self.assertIn("deactivate_clinic", actions)
        # Todas las entradas son del propio superadmin
        self.assertTrue(all(r["user"] == "sa@plataforma.ec" for r in resp.data["results"]))


class PlatformConfigTests(PlatformBase):
    def test_get_and_update_config(self):
        resp = self.client.get("/api/v1/platform/config/")
        self.assertEqual(resp.data["currency"], "USD")
        resp = self.client.patch("/api/v1/platform/config/", {
            "platform_name": "OdontoSaaS", "smtp_host": "smtp.zoho.com",
            "smtp_password": "secretisimo",
        })
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data["platform_name"], "OdontoSaaS")
        # La contraseña SMTP jamás vuelve en la respuesta
        self.assertNotIn("smtp_password", resp.data)
        self.assertTrue(resp.data["smtp_password_set"])
        config = PlatformConfiguration.get_solo()
        self.assertEqual(config.smtp_password, "secretisimo")
