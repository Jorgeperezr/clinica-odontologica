"""Tests Sprint 22: plantillas, presupuesto automático, progreso,
seguimientos, documentos con categorías clínicas y receta PDF."""

from datetime import date, timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.agenda.models import Doctor
from apps.common.models import Tenant
from apps.patients.models import Patient


class Sprint22Base(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Clínica S22", ruc="1791234567001",
            address="Av. Central 123", phone="+59372570001",
        )
        self.admin = User.objects.create_user(
            email="admin@s22.ec", password="superseguro123", role="admin", tenant=self.tenant,
        )
        du = User.objects.create_user(
            email="doc@s22.ec", password="superseguro123", role="doctor",
            tenant=self.tenant, full_name="Dra. Sofía Vega",
        )
        self.doctor = Doctor.objects.create(
            tenant=self.tenant, user=du, license_number="MSP-12345",
        )
        self.doctor_user = du
        self.patient = Patient.objects.create(
            tenant=self.tenant, first_name="Luis", last_name="Paz", national_id="1102003001",
        )
        from apps.specialties.models import Specialty
        from apps.configuration.models import Treatment
        spec = Specialty.objects.create(tenant=self.tenant, name="Rehab S22")
        self.t1 = Treatment.objects.create(
            tenant=self.tenant, specialty=spec, name="Corona S22", base_price=Decimal("300.00"),
        )
        self.t2 = Treatment.objects.create(
            tenant=self.tenant, specialty=spec, name="Limpieza S22", base_price=Decimal("50.00"),
        )


class TemplateAndBudgetTests(Sprint22Base):
    def test_template_apply_and_auto_budget_with_progress(self):
        self.client.force_authenticate(user=self.admin)

        # Crear plantilla con 2 ítems
        resp = self.client.post("/api/v1/clinical/plan-templates/", {
            "name": "Rehabilitación básica",
            "description": "Protocolo estándar",
            "items": [
                {"treatment": str(self.t1.id), "order": 1},
                {"treatment": str(self.t2.id), "order": 2},
            ],
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)
        template_id = resp.data["id"]

        # Listar: total estimado = 350
        resp = self.client.get("/api/v1/clinical/plan-templates/")
        self.assertEqual(resp.data[0]["total_estimated"], "350.00")

        # Aplicar al paciente → plan con 2 ítems y progreso 0%
        resp = self.client.post(
            f"/api/v1/patients/{self.patient.id}/apply-plan-template/",
            {"template_id": template_id},
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        plan_id = resp.data["id"]
        self.assertEqual(len(resp.data["items"]), 2)
        self.assertEqual(resp.data["progress"], {"done": 0, "total": 2, "percent": 0})
        item1 = resp.data["items"][0]["id"]

        # Presupuesto automático desde el plan
        resp = self.client.post(f"/api/v1/treatment-plans/{plan_id}/generate-budget/")
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data["total_amount"], "350.00")
        self.assertEqual(len(resp.data["items"]), 2)

        # Progreso: marcar 1 de 2 como realizado → 50%
        resp = self.client.patch(f"/api/v1/treatment-plan-items/{item1}/", {"status": "done"})
        self.assertEqual(resp.status_code, 200, resp.content)
        resp = self.client.get(f"/api/v1/patients/{self.patient.id}/treatment-plans/")
        plans = resp.data.get("results", resp.data)
        self.assertEqual(plans[0]["progress"], {"done": 1, "total": 2, "percent": 50})


class FollowUpTests(Sprint22Base):
    def test_follow_up_alerts_due_and_overdue(self):
        from apps.clinical.models import Evolution
        Evolution.objects.create(
            tenant=self.tenant, patient=self.patient, created_by=self.admin,
            type="clinical_note", date=date.today() - timedelta(days=10),
            notes="Control en 7 días", follow_up_date=date.today() - timedelta(days=3),
        )
        Evolution.objects.create(
            tenant=self.tenant, patient=self.patient, created_by=self.admin,
            type="clinical_note", date=date.today(), notes="Futuro",
            follow_up_date=date.today() + timedelta(days=30),  # NO debe alertar
        )
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get("/api/v1/clinical/follow-ups/")
        self.assertEqual(len(resp.data["results"]), 1)
        self.assertEqual(resp.data["results"][0]["days_overdue"], 3)


class DocumentTests(Sprint22Base):
    def test_upload_clinical_photo(self):
        self.client.force_authenticate(user=self.admin)
        file = SimpleUploadedFile("rx-16.png", b"fake-image-bytes", content_type="image/png")
        resp = self.client.post(f"/api/v1/patients/{self.patient.id}/documents/", {
            "doc_type": "radiograph", "description": "Rx periapical pieza 16", "file": file,
        }, format="multipart")
        self.assertEqual(resp.status_code, 201, resp.content)
        resp = self.client.get(f"/api/v1/patients/{self.patient.id}/documents/")
        docs = resp.data.get("results", resp.data)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["doc_type"], "radiograph")


class PrescriptionPDFTests(Sprint22Base):
    def test_prescription_pdf_generated(self):
        from apps.clinical.models import Evolution
        evo = Evolution.objects.create(
            tenant=self.tenant, patient=self.patient,
            doctor=self.doctor, created_by=self.doctor_user,
            type="prescription", date=date.today(),
            notes="Amoxicilina 500mg\nCada 8 horas por 7 días",
        )
        self.client.force_authenticate(user=self.doctor_user)
        resp = self.client.get(f"/api/v1/evolutions/{evo.id}/prescription-pdf/")
        self.assertEqual(resp.status_code, 200)
        body = b"".join(resp.streaming_content)
        self.assertTrue(body.startswith(b"%PDF"))

    def test_non_prescription_404(self):
        from apps.clinical.models import Evolution
        evo = Evolution.objects.create(
            tenant=self.tenant, patient=self.patient, created_by=self.admin,
            type="clinical_note", date=date.today(), notes="No es receta",
        )
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(f"/api/v1/evolutions/{evo.id}/prescription-pdf/")
        self.assertEqual(resp.status_code, 404)


class DoctorSignatureTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="T firma")
        du = User.objects.create_user(
            email="d@firma.ec", password="superseguro123", role="doctor",
            tenant=self.tenant, full_name="Dra. Firma",
        )
        self.doctor = Doctor.objects.create(tenant=self.tenant, user=du)
        self.doctor_user = du

    def test_doctor_saves_and_reads_own_signature(self):
        self.client.force_authenticate(user=self.doctor_user)
        png_1px = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAf"
                   "FcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
        resp = self.client.post("/api/v1/doctors/me/signature/", {
            "signature_image": png_1px, "license_number": "MSP-12345",
        })
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data["has_signature"])
        resp = self.client.get("/api/v1/doctors/me/signature/")
        self.assertEqual(resp.data["license_number"], "MSP-12345")
        self.assertTrue(resp.data["signature_image"].startswith("data:image/png"))

    def test_reception_cannot_use_signature_endpoint(self):
        r = User.objects.create_user(
            email="r@firma.ec", password="superseguro123", role="reception", tenant=self.tenant,
        )
        self.client.force_authenticate(user=r)
        self.assertEqual(self.client.get("/api/v1/doctors/me/signature/").status_code, 403)

    def test_prescription_pdf_with_signature(self):
        from datetime import date
        from apps.clinical.models import Evolution
        self.doctor.signature_image = (
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAf"
            "FcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        self.doctor.save()
        patient = Patient.objects.create(
            tenant=self.tenant, first_name="Rx", last_name="Firmada", national_id="4040404040",
        )
        evo = Evolution.objects.create(
            tenant=self.tenant, patient=patient, doctor=self.doctor,
            type="prescription", date=date.today(), notes="Amoxicilina 500mg c/8h por 7 días",
        )
        self.client.force_authenticate(user=self.doctor_user)
        resp = self.client.get(f"/api/v1/evolutions/{evo.id}/prescription-pdf/")
        self.assertEqual(resp.status_code, 200)
        body = b"".join(resp.streaming_content) if hasattr(resp, "streaming_content") else resp.content
        self.assertTrue(body.startswith(b"%PDF"))


class TemplateItemsAPITests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="T titem")
        self.admin = User.objects.create_user(
            email="a@titem.ec", password="superseguro123", role="admin", tenant=self.tenant,
        )
        from apps.specialties.models import Specialty
        from apps.configuration.models import Treatment
        sp = Specialty.objects.create(tenant=self.tenant, name="Esp TI")
        self.treatment = Treatment.objects.create(
            tenant=self.tenant, specialty=sp, name="Trat TI", base_price="120.00",
        )

    def test_build_template_via_api(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post("/api/v1/clinical/plan-templates/", {
            "name": "Plantilla API", "description": "vía panel",
        })
        self.assertEqual(resp.status_code, 201, resp.content)
        template_id = resp.data["id"]

        resp = self.client.post(f"/api/v1/clinical/plan-templates/{template_id}/items/", {
            "treatment": str(self.treatment.id),
        })
        self.assertEqual(resp.status_code, 201, resp.content)
        item_id = resp.data["id"]

        resp = self.client.get("/api/v1/clinical/plan-templates/")
        tpl = next(t for t in resp.data if t["id"] == template_id)
        self.assertEqual(len(tpl["items"]), 1)
        self.assertEqual(tpl["total_estimated"], "120.00")

        resp = self.client.delete(f"/api/v1/clinical/plan-template-items/{item_id}/")
        self.assertEqual(resp.status_code, 204)


class Form033FrontendContractTests(APITestCase):
    """Contrato exacto que consume Form033Panel.js (Sprint 23)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="T 033fe")
        du = User.objects.create_user(
            email="d@033.ec", password="superseguro123", role="doctor",
            tenant=self.tenant, full_name="Dra. MSP",
        )
        self.doctor = Doctor.objects.create(tenant=self.tenant, user=du, license_number="MSP-777")
        self.doctor_user = du
        self.patient = Patient.objects.create(
            tenant=self.tenant, first_name="Form", last_name="MSP", national_id="5050505050",
        )

    def test_create_form033_with_msp_literals(self):
        self.client.force_authenticate(user=self.doctor_user)
        resp = self.client.post(f"/api/v1/patients/{self.patient.id}/form033/", {
            "date": "2026-07-11",
            "motivo_consulta": "Dolor en molar inferior",
            "embarazada": False,
            "enfermedad_actual": "Dolor de 3 días",
            "antecedentes_personales": {"Diabetes": {"checked": True, "detail": ""}},
            "antecedentes_familiares": {"Cáncer": {"checked": True, "detail": ""}},
            "examen_estomatognatico": {"Lengua": "Saburral"},
            "temperatura": "36.8", "pulso": 72,
            "frecuencia_respiratoria": 16, "presion_arterial": "120/80",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)
        # Literal O: se arma solo desde la credencial (oculto en la UI)
        self.assertIn("Dra. MSP", resp.data["registered_by"])
        self.assertIn("MSP-777", resp.data["registered_by"])

        # El GET lo lista para el panel
        resp = self.client.get(f"/api/v1/patients/{self.patient.id}/form033/")
        data = resp.data if isinstance(resp.data, list) else resp.data.get("results", [])
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["antecedentes_personales"]["Diabetes"]["checked"], True)

    def test_cie10_search_by_code_and_name(self):
        self.client.force_authenticate(user=self.doctor_user)
        # Por código
        resp = self.client.get("/api/v1/cie10/?q=K02")
        codes = [r["code"] for r in resp.data["results"]]
        self.assertTrue(any(c.startswith("K02") for c in codes))
        # Por nombre
        resp = self.client.get("/api/v1/cie10/?q=caries")
        self.assertTrue(len(resp.data["results"]) > 0)


class DiagnosisKindTests(APITestCase):
    """Literal N: diagnóstico con CIE-10 y tipo PRE/DEF."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="T diagN")
        du = User.objects.create_user(
            email="d@diagn.ec", password="superseguro123", role="doctor",
            tenant=self.tenant, full_name="Dra. Dx",
        )
        Doctor.objects.create(tenant=self.tenant, user=du)
        self.doctor_user = du
        self.patient = Patient.objects.create(
            tenant=self.tenant, first_name="Dx", last_name="Test", national_id="6060606060",
        )

    def test_create_diagnosis_with_kind(self):
        self.client.force_authenticate(user=self.doctor_user)
        resp = self.client.post(f"/api/v1/patients/{self.patient.id}/diagnoses/", {
            "code": "K02.1", "description": "Caries de la dentina",
            "tooth_fdi_code": "16", "diagnosis_kind": "def", "date": "2026-07-12",
        })
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data["diagnosis_kind"], "def")
        self.assertEqual(resp.data["kind_display"], "Definitivo")


class CpoCeoAndExportTests(APITestCase):
    """Sprint 25: índices CPO-ceo (J) y export del formulario 033 a PDF."""

    def setUp(self):
        from django.core.management import call_command
        self.tenant = Tenant.objects.create(name="T cpo")
        call_command("bootstrap", tenant_name=self.tenant.name)
        du = User.objects.create_user(
            email="d@cpo.ec", password="superseguro123", role="doctor",
            tenant=self.tenant, full_name="Dra. CPO", 
        )
        self.doctor = Doctor.objects.create(tenant=self.tenant, user=du, license_number="MSP-999")
        self.doctor_user = du
        self.patient = Patient.objects.create(
            tenant=self.tenant, first_name="Cpo", last_name="Test", national_id="7070707070",
        )

    def _set_tooth(self, fdi, code):
        from apps.clinical.models import OdontogramState, ToothRecord
        state = OdontogramState.objects.get(tenant=self.tenant, code=code)
        ToothRecord.objects.create(
            tenant=self.tenant, patient=self.patient, tooth_fdi_code=fdi,
            surface="whole", state=state, date="2026-07-12",
        )

    def test_cpo_ceo_calculation(self):
        # Permanentes: caries en 16, obturado en 26, extracción indicada en 36
        self._set_tooth("16", "CARIES")
        self._set_tooth("26", "OBTURADO")
        self._set_tooth("36", "INDICADA_EXTRACCION")
        # Temporal: caries en 55
        self._set_tooth("55", "CARIES")
        self.client.force_authenticate(user=self.doctor_user)
        resp = self.client.get(f"/api/v1/patients/{self.patient.id}/cpo-ceo/")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data["cpo"]["C"], 1)
        self.assertEqual(resp.data["cpo"]["O"], 1)
        self.assertEqual(resp.data["cpo"]["P"], 1)
        self.assertEqual(resp.data["cpo"]["total"], 3)
        self.assertEqual(resp.data["ceo"]["c"], 1)
        self.assertEqual(resp.data["ceo"]["total"], 1)

    def test_form033_pdf_export(self):
        self._set_tooth("16", "CARIES")
        self.client.force_authenticate(user=self.doctor_user)
        # Crear una consulta 033 para que el PDF tenga contenido
        self.client.post(f"/api/v1/patients/{self.patient.id}/form033/", {
            "date": "2026-07-12", "motivo_consulta": "Control",
            "antecedentes_personales": {}, "antecedentes_familiares": {},
            "examen_estomatognatico": {},
        }, format="json")
        resp = self.client.get(f"/api/v1/patients/{self.patient.id}/form033/export-pdf/")
        self.assertEqual(resp.status_code, 200)
        body = b"".join(resp.streaming_content) if hasattr(resp, "streaming_content") else resp.content
        self.assertTrue(body.startswith(b"%PDF"))


class OdontogramSurfaceTests(APITestCase):
    """Sprint 26: registro por superficie + recesión/movilidad por pieza."""

    def setUp(self):
        from django.core.management import call_command
        self.tenant = Tenant.objects.create(name="T surf")
        call_command("bootstrap", tenant_name=self.tenant.name)
        du = User.objects.create_user(
            email="d@surf.ec", password="superseguro123", role="doctor",
            tenant=self.tenant, full_name="Dra. Surf",
        )
        Doctor.objects.create(tenant=self.tenant, user=du)
        self.doctor_user = du
        self.patient = Patient.objects.create(
            tenant=self.tenant, first_name="Sur", last_name="Face", national_id="8080808080",
        )

    def test_register_state_on_specific_surface(self):
        from apps.clinical.models import OdontogramState
        caries = OdontogramState.objects.get(tenant=self.tenant, code="CARIES")
        self.client.force_authenticate(user=self.doctor_user)
        resp = self.client.post(f"/api/v1/patients/{self.patient.id}/tooth-records/", {
            "tooth_fdi_code": "16", "surface": "occlusal", "state": str(caries.id),
            "date": "2026-07-13",
        })
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data["surface"], "occlusal")

        # El odontograma actual devuelve la superficie pintada
        resp = self.client.get(f"/api/v1/patients/{self.patient.id}/odontogram/current/")
        teeth = resp.data["teeth"]
        occ = [t for t in teeth if t["tooth_fdi_code"] == "16" and t["surface"] == "occlusal"]
        self.assertEqual(len(occ), 1)

    def test_register_mobility_and_recession(self):
        from apps.clinical.models import OdontogramState
        sano = OdontogramState.objects.get(tenant=self.tenant, code="SANO")
        self.client.force_authenticate(user=self.doctor_user)
        resp = self.client.post(f"/api/v1/patients/{self.patient.id}/tooth-records/", {
            "tooth_fdi_code": "21", "surface": "whole", "state": str(sano.id),
            "mobility": 2, "recession": 3, "date": "2026-07-13",
        })
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data["mobility"], 2)
        self.assertEqual(resp.data["recession"], 3)


class OralHealthIndicatorsTests(APITestCase):
    """Literal I: indicadores de salud bucal guardados en el Form033."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="T ind")
        du = User.objects.create_user(
            email="d@ind.ec", password="superseguro123", role="doctor",
            tenant=self.tenant, full_name="Dra. Ind",
        )
        Doctor.objects.create(tenant=self.tenant, user=du)
        self.doctor_user = du
        self.patient = Patient.objects.create(
            tenant=self.tenant, first_name="Ind", last_name="Bucal", national_id="9090909090",
        )

    def test_save_and_read_indicators(self):
        self.client.force_authenticate(user=self.doctor_user)
        indicadores = {
            "higiene": {"16": {"placa": 2, "calculo": 1, "gingivitis": 1}},
            "enfermedad_periodontal": "moderada",
            "oclusion": "II",
            "fluorosis": "leve",
        }
        # Crear el Form033 con indicadores
        resp = self.client.post(f"/api/v1/patients/{self.patient.id}/form033/", {
            "date": "2026-07-13", "indicadores_salud_bucal": indicadores,
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)
        record_id = resp.data["id"]

        # Leerlo de vuelta
        resp = self.client.get(f"/api/v1/patients/{self.patient.id}/form033/")
        data = resp.data if isinstance(resp.data, list) else resp.data.get("results", [])
        self.assertEqual(data[0]["indicadores_salud_bucal"]["oclusion"], "II")

        # Actualizarlo vía PATCH del detalle
        indicadores["fluorosis"] = "severa"
        resp = self.client.patch(f"/api/v1/form033/{record_id}/", {
            "indicadores_salud_bucal": indicadores,
        }, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data["indicadores_salud_bucal"]["fluorosis"], "severa")
