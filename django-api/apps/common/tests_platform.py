"""
Tests de la capa SaaS: Super Administrador, gestión de clínicas y —
lo más crítico— el AISLAMIENTO de datos entre clínicas.
"""

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.common.models import Tenant


class PlatformTests(APITestCase):
    def setUp(self):
        self.superadmin = User.objects.create_user(
            email="sa@plataforma.ec", password="superseguro123",
            role="superadmin", tenant=None, full_name="Super Admin",
        )

    def test_superadmin_creates_clinic_with_seeded_catalog(self):
        self.client.force_authenticate(user=self.superadmin)
        resp = self.client.post("/api/v1/platform/clinics/", {
            "name": "Clínica Norte", "ruc": "1111111111001",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)
        tenant = Tenant.objects.get(name="Clínica Norte")

        # El bootstrap sembró el catálogo de la clínica nueva
        from apps.clinical.models import OdontogramState
        from apps.configuration.models import SystemParameter
        from apps.specialties.models import Specialty
        self.assertEqual(OdontogramState.objects.filter(tenant=tenant).count(), 12)
        self.assertTrue(Specialty.objects.filter(tenant=tenant).exists())
        self.assertTrue(SystemParameter.objects.filter(tenant=tenant).exists())

    def test_duplicate_clinic_name_rejected(self):
        Tenant.objects.create(name="Clínica Sur")
        self.client.force_authenticate(user=self.superadmin)
        resp = self.client.post("/api/v1/platform/clinics/", {"name": "clínica sur"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_superadmin_creates_clinic_admin(self):
        tenant = Tenant.objects.create(name="Clínica Este")
        self.client.force_authenticate(user=self.superadmin)
        resp = self.client.post(f"/api/v1/platform/clinics/{tenant.id}/admin/", {
            "email": "admin@este.ec", "full_name": "Ana Este", "password": "ClaveSegura26",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)
        admin = User.objects.get(email="admin@este.ec")
        self.assertEqual(admin.role, "admin")
        self.assertEqual(admin.tenant, tenant)
        self.assertTrue(admin.check_password("ClaveSegura26"))

    def test_clinic_admin_cannot_access_platform(self):
        tenant = Tenant.objects.create(name="Clínica Oeste")
        clinic_admin = User.objects.create_user(
            email="admin@oeste.ec", password="superseguro123",
            role="admin", tenant=tenant,
        )
        self.client.force_authenticate(user=clinic_admin)
        for url in ["/api/v1/platform/clinics/", "/api/v1/platform/overview/"]:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN, url)

    def test_data_isolation_between_clinics(self):
        """CRÍTICO: el staff de una clínica jamás ve datos de otra."""
        from apps.patients.models import Patient

        clinic_a = Tenant.objects.create(name="Clínica A")
        clinic_b = Tenant.objects.create(name="Clínica B")
        admin_a = User.objects.create_user(
            email="a@a.ec", password="superseguro123", role="admin", tenant=clinic_a,
        )
        admin_b = User.objects.create_user(
            email="b@b.ec", password="superseguro123", role="admin", tenant=clinic_b,
        )
        Patient.objects.create(
            tenant=clinic_a, first_name="Paciente", last_name="DeA", national_id="0101010101",
        )

        # El admin de A ve a su paciente
        self.client.force_authenticate(user=admin_a)
        resp = self.client.get("/api/v1/patients/")
        results = resp.data.get("results", resp.data)
        self.assertEqual(len(results), 1)

        # El admin de B NO ve nada de A
        self.client.force_authenticate(user=admin_b)
        resp = self.client.get("/api/v1/patients/")
        results = resp.data.get("results", resp.data)
        self.assertEqual(len(results), 0)

        # Y B tampoco puede leer al paciente de A por ID directo
        patient_a = Patient.objects.get(national_id="0101010101")
        resp = self.client.get(f"/api/v1/patients/{patient_a.id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_deactivated_clinic_users_are_blocked(self):
        """Al desactivar una clínica, sus usuarios pierden acceso (aun con token vigente)."""
        from rest_framework_simplejwt.tokens import RefreshToken

        tenant = Tenant.objects.create(name="Clínica Baja")
        user = User.objects.create_user(
            email="staff@baja.ec", password="superseguro123", role="admin", tenant=tenant,
        )
        token = str(RefreshToken.for_user(user).access_token)

        # Con la clínica activa, el token funciona
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        resp = self.client.get("/api/v1/patients/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # El superadmin desactiva la clínica
        tenant.is_active = False
        tenant.save()

        # El mismo token ahora es rechazado
        resp = self.client.get("/api/v1/patients/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_overview_counts(self):
        Tenant.objects.create(name="C1")
        Tenant.objects.create(name="C2", is_active=False)
        self.client.force_authenticate(user=self.superadmin)
        resp = self.client.get("/api/v1/platform/overview/")
        self.assertEqual(resp.data["clinics_total"], 2)
        self.assertEqual(resp.data["clinics_active"], 1)
