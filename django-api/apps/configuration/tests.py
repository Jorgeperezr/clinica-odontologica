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


class ClinicBrandingTests(APITestCase):
    """Sprint 33: identidad visual por clínica (logo + tema)."""

    def setUp(self):
        from apps.common.models import Tenant
        self.tenant = Tenant.objects.create(name="T brand")
        self.admin = User.objects.create_user(
            email="a@brand.ec", password="superseguro123", role="admin", tenant=self.tenant,
        )
        self.reception = User.objects.create_user(
            email="r@brand.ec", password="superseguro123", role="reception", tenant=self.tenant,
        )

    def _png(self, color):
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (64, 64), color).save(buf, format="PNG")
        buf.seek(0)
        buf.name = "logo.png"
        return buf

    def test_theme_saved_per_tenant_and_readable_by_all_roles(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch("/api/v1/config/branding/", {
            "theme": {"preset": "custom", "primary": "#7b1e3c", "secondary": "#f2c14e"},
        }, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data["theme"]["primary"], "#7b1e3c")

        # Recepción puede LEER el tema (se aplica a toda la interfaz)
        self.client.force_authenticate(user=self.reception)
        resp = self.client.get("/api/v1/config/branding/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["theme"]["primary"], "#7b1e3c")

        # ...pero no modificarlo
        resp = self.client.patch("/api/v1/config/branding/", {
            "theme": {"preset": "default"},
        }, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_logo_upload_extracts_palette_and_clear_removes(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch(
            "/api/v1/config/branding/",
            {"logo": self._png((123, 30, 60))},  # vino
            format="multipart",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIsNotNone(resp.data["logo_url"])
        # La paleta extraída refleja el color dominante del logo
        self.assertIn("auto_palette", resp.data)
        primary = resp.data["auto_palette"]["primary"]
        self.assertTrue(primary.startswith("#") and len(primary) == 7)
        r = int(primary[1:3], 16)
        self.assertGreater(r, 80)  # componente rojo dominante

        # Eliminar el logotipo
        resp = self.client.patch("/api/v1/config/branding/", {"logo_clear": "true"})
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data["logo_url"])

    def test_branding_isolated_between_tenants(self):
        from apps.common.models import Tenant
        other = Tenant.objects.create(name="T brand 2")
        other_admin = User.objects.create_user(
            email="a2@brand.ec", password="superseguro123", role="admin", tenant=other,
        )
        self.client.force_authenticate(user=self.admin)
        self.client.patch("/api/v1/config/branding/", {
            "theme": {"preset": "custom", "primary": "#111111", "secondary": ""},
        }, format="json")

        self.client.force_authenticate(user=other_admin)
        resp = self.client.get("/api/v1/config/branding/")
        self.assertEqual(resp.data["theme"].get("preset", "default"), "default")


class ClinicBrandingNamesTests(APITestCase):
    """Sprint 34: nombre comercial y corto por clínica."""

    def test_names_saved_and_readable_by_all_roles(self):
        from apps.common.models import Tenant
        tenant = Tenant.objects.create(name="T names")
        admin = User.objects.create_user(
            email="a@names.ec", password="superseguro123", role="admin", tenant=tenant,
        )
        doctor = User.objects.create_user(
            email="d@names.ec", password="superseguro123", role="doctor", tenant=tenant,
        )
        self.client.force_authenticate(user=admin)
        resp = self.client.patch("/api/v1/config/branding/", {
            "display_name": "Clínica Dental Sonrisa Sana",
            "short_name": "Sonrisa Sana",
        }, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data["display_name"], "Clínica Dental Sonrisa Sana")

        self.client.force_authenticate(user=doctor)
        resp = self.client.get("/api/v1/config/branding/")
        self.assertEqual(resp.data["short_name"], "Sonrisa Sana")


class DocumentAppearanceTests(APITestCase):
    """
    Motor global de estilos de documentos (Sprint 60).
    """

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Doc")
        self.admin = User.objects.create_user(
            email="admin@doc.ec", password="superseguro123", role="admin", tenant=self.tenant)
        self.doctor = User.objects.create_user(
            email="doc@doc.ec", password="superseguro123", role="doctor", tenant=self.tenant)

    def test_defaults_are_served_without_configuring_anything(self):
        """Sin configurar nada, el endpoint devuelve la apariencia por defecto completa."""
        self.client.force_authenticate(user=self.doctor)
        resp = self.client.get("/api/v1/config/document-appearance/")
        self.assertEqual(resp.status_code, 200)
        for group in ("header", "footer", "typography", "palette",
                      "tables", "page", "logo", "signature", "watermark"):
            self.assertIn(group, resp.data)
        self.assertEqual(resp.data["page"]["size"], "A4")

    def test_only_admin_can_change_appearance(self):
        self.client.force_authenticate(user=self.doctor)
        resp = self.client.patch("/api/v1/config/document-appearance/",
                                 {"page": {"size": "LETTER"}}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_patch_merges_instead_of_replacing(self):
        """
        Enviar un grupo parcial no debe borrar el resto de sus ajustes: el
        panel manda solo lo que el usuario toca.
        """
        self.client.force_authenticate(user=self.admin)
        resp = self.client.patch("/api/v1/config/document-appearance/",
                                 {"page": {"size": "LETTER"}}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["page"]["size"], "LETTER")
        # Los márgenes, que no se enviaron, siguen en su valor por defecto
        self.assertEqual(resp.data["page"]["margin_top_mm"], 20)

    def test_style_engine_reflects_saved_configuration(self):
        """El motor central debe servir lo que la clínica configuró."""
        from apps.common.document_style import get_document_style

        self.client.force_authenticate(user=self.admin)
        self.client.patch("/api/v1/config/document-appearance/", {
            "page": {"size": "LETTER", "orientation": "landscape"},
            "typography": {"family": "Times", "size_pt": 12},
            "palette": {"primary": "#123456"},
        }, format="json")

        style = get_document_style(self.tenant)
        self.assertGreater(style.width, style.height)      # apaisado
        self.assertEqual(style.font, "Times-Roman")
        self.assertEqual(style.size, 12)
        self.assertEqual(style.primary.hexval()[2:], "123456")

    def test_appearance_is_isolated_between_clinics(self):
        from apps.common.document_style import get_document_style

        other = Tenant.objects.create(name="Otra Clínica")
        self.client.force_authenticate(user=self.admin)
        self.client.patch("/api/v1/config/document-appearance/",
                          {"palette": {"primary": "#abcdef"}}, format="json")

        self.assertEqual(get_document_style(self.tenant).primary.hexval()[2:], "abcdef")
        # La otra clínica conserva el color por defecto
        self.assertNotEqual(get_document_style(other).primary.hexval()[2:], "abcdef")

    def test_generated_document_uses_the_configured_appearance(self):
        """
        Prueba de punta a punta del motor: cambiar la hoja a apaisado debe
        cambiar el PDF que emite un generador real.
        """
        from apps.clinical.exam_request_pdf import build_exam_request_pdf
        from apps.common.document_style import get_document_style
        from datetime import datetime

        args = dict(
            clinic={"name": "Clínica Doc", "address": "", "phone": "", "email": ""},
            professional={"full_name": "Dra. Ruiz", "specialty": "Endodoncia",
                          "license_number": "1"},
            patient={"full_name": "Juan Pérez", "national_id": "1", "age": "30",
                     "sex": "M", "history_number": "1"},
            exam={"datetime": datetime.now(), "category": "Rayos X", "detail": "Periapical",
                  "justification": "Dolor", "observations": "", "priority": "Normal",
                  "urgent": False},
        )
        before = build_exam_request_pdf(style=get_document_style(self.tenant), **args)
        self.assertTrue(before.startswith(b"%PDF"))

        self.client.force_authenticate(user=self.admin)
        self.client.patch("/api/v1/config/document-appearance/",
                          {"page": {"orientation": "landscape"},
                           "watermark": {"enabled": True, "text": "COPIA"}}, format="json")

        after = build_exam_request_pdf(style=get_document_style(self.tenant), **args)
        self.assertTrue(after.startswith(b"%PDF"))
        self.assertNotEqual(before, after)

    def test_reset_restores_defaults(self):
        self.client.force_authenticate(user=self.admin)
        self.client.patch("/api/v1/config/document-appearance/",
                          {"page": {"size": "LEGAL"}}, format="json")
        resp = self.client.delete("/api/v1/config/document-appearance/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["page"]["size"], "A4")
