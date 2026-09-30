"""
Respaldo descargable: el paquete con las herramientas para abrirlo sin
la plataforma, y la copia de cada profesional.

Lo que se fija aquí:

  · que lo descargado se pueda abrir SIN la plataforma: descifrar.py
    abre la copia que genera el servidor, desde el .clinicabk y desde el
    .zip, y falla limpio con la frase equivocada;
  · que la copia de un doctor lleve sus pacientes y nada más: ni los de
    un colega, ni cobros, ni auditoría, ni el resto del personal;
  · que un profesional solo abra en el panel las copias suyas.
"""

import io
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from datetime import date, timedelta
from pathlib import Path

from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import AuditLog, User
from apps.agenda.models import Appointment, Doctor
from apps.clinical.models import Evolution
from apps.common.models import Tenant
from apps.common.paquete_respaldo import KIT, empaquetar, sacar_copia
from apps.common.tenant_backup import BackupError, build_encrypted, read_encrypted
from apps.patients.models import MedicalBackground, Patient

FRASE = "frase-larga-de-prueba"
DESCIFRAR_PY = KIT / "descifrar.py"


def modelos(payload):
    return {r["model"] for r in payload["records"]}


def cedulas(payload):
    return {r["fields"]["national_id"] for r in payload["records"] if r["model"] == "patients.patient"}


class Base(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Sonrisa", ruc="1790012345001")
        self.admin = User.objects.create_user(email="admin@sonrisa.ec", password="superseguro123",
                                              role="admin", tenant=self.tenant)
        self.recepcion = User.objects.create_user(email="recep@sonrisa.ec", password="superseguro123",
                                                  role="reception", tenant=self.tenant)
        self.u_ana = User.objects.create_user(email="ana@sonrisa.ec", password="superseguro123",
                                              role="doctor", tenant=self.tenant, full_name="Dra. Ana Ríos")
        self.u_luis = User.objects.create_user(email="luis@sonrisa.ec", password="superseguro123",
                                               role="doctor", tenant=self.tenant, full_name="Dr. Luis Mora")
        self.auxiliar = User.objects.create_user(email="aux@sonrisa.ec", password="superseguro123",
                                                 role="auxiliary", tenant=self.tenant)
        self.ana = Doctor.objects.create(tenant=self.tenant, user=self.u_ana)
        self.luis = Doctor.objects.create(tenant=self.tenant, user=self.u_luis)

        def paciente(cedula):
            return Patient.objects.create(tenant=self.tenant, first_name="P", last_name=cedula,
                                          national_id=cedula)

        # Con cita de Ana; con una evolución que escribió Ana sin cita;
        # y solo de Luis.
        self.con_cita, self.con_nota, self.de_luis = paciente("111"), paciente("222"), paciente("333")
        inicio = timezone.now() + timedelta(days=1)
        Appointment.objects.create(tenant=self.tenant, patient=self.con_cita, doctor=self.ana,
                                   scheduled_start=inicio, scheduled_end=inicio + timedelta(minutes=30))
        Appointment.objects.create(tenant=self.tenant, patient=self.de_luis, doctor=self.luis,
                                   scheduled_start=inicio, scheduled_end=inicio + timedelta(minutes=30))
        Evolution.objects.create(tenant=self.tenant, patient=self.con_nota, created_by=self.u_ana,
                                 date=date.today(), notes="Control")
        # Algo que Luis escribió en un paciente de Ana: es historia de ese
        # paciente, así que va en la copia de Ana.
        Evolution.objects.create(tenant=self.tenant, patient=self.con_cita, doctor=self.luis,
                                 date=date.today(), notes="Interconsulta")
        MedicalBackground.objects.create(patient=self.con_cita, allergies="Penicilina")
        AuditLog.objects.create(tenant=self.tenant, user=self.admin, action="x", entity_type="y")

        self.url = reverse("tenant-backup")
        self.url_abrir = reverse("tenant-backup-decrypt")

    def descargar(self, usuario):
        self.client.force_authenticate(user=usuario)
        r = self.client.post(self.url, {"passphrase": FRASE, "passphrase_confirm": FRASE})
        self.assertEqual(r.status_code, 200, getattr(r, "data", None))
        return r

    def abrir(self, usuario, contenido, nombre="copia.clinicabk"):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_authenticate(user=usuario)
        return self.client.post(self.url_abrir, {"file": SimpleUploadedFile(nombre, contenido),
                                                 "passphrase": FRASE})


class PaqueteDeDescarga(Base):
    def test_el_zip_trae_la_copia_las_instrucciones_y_las_herramientas(self):
        r = self.descargar(self.admin)
        self.assertEqual(r["Content-Type"], "application/zip")
        self.assertRegex(r["Content-Disposition"], r'filename="respaldo-clinica-sonrisa-[\d_-]+\.zip"')
        z = zipfile.ZipFile(io.BytesIO(r.content))
        nombres = z.namelist()
        [copia] = [n for n in nombres if n.endswith(".clinicabk")]
        self.assertEqual(set(nombres) - {copia}, {"COMO-DESCIFRAR.txt", "descifrar.html", "descifrar.py"})
        # La copia va sin comprimir: así la lee descifrar.html sin más.
        self.assertEqual(z.getinfo(copia).compress_type, zipfile.ZIP_STORED)

        texto = z.read("COMO-DESCIFRAR.txt").decode("utf-8")
        self.assertIn("Clínica Sonrisa", texto)
        self.assertIn(copia, texto)
        self.assertIn("todos los datos de la clínica", texto)
        self.assertIn("PBKDF2-HMAC-SHA256", texto)
        self.assertNotIn("$", texto)           # ninguna variable sin sustituir
        self.assertNotIn(FRASE.encode(), r.content)

    def test_la_copia_del_profesional_se_nombra_y_se_explica_como_suya(self):
        r = self.descargar(self.u_ana)
        self.assertIn("respaldo-clinica-sonrisa-dra-ana-rios-", r["Content-Disposition"])
        texto = zipfile.ZipFile(io.BytesIO(r.content)).read("COMO-DESCIFRAR.txt").decode("utf-8")
        self.assertIn("pacientes de Dra. Ana Ríos (2)", texto)

    def test_herramientas_sueltas_sin_datos(self):
        self.client.force_authenticate(user=self.u_ana)
        r = self.client.get(reverse("tenant-backup-tools"))
        self.assertEqual(r.status_code, 200)
        nombres = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
        self.assertEqual(sorted(nombres), ["COMO-DESCIFRAR.txt", "descifrar.html", "descifrar.py"])
        self.client.force_authenticate(user=self.recepcion)
        self.assertEqual(self.client.get(reverse("tenant-backup-tools")).status_code, 403)

    def test_el_panel_abre_tambien_el_zip(self):
        r = self.abrir(self.admin, self.descargar(self.admin).content, "respaldo.zip")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["manifest"]["alcance"], {"tipo": "clinica"})

    def test_un_zip_sin_copia_no_se_abre(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("otra-cosa.txt", "hola")
        self.assertEqual(self.abrir(self.admin, buf.getvalue(), "x.zip").status_code, 400)


class CopiaDelProfesional(Base):
    def copia(self, usuario):
        return read_encrypted(sacar_copia(self.descargar(usuario).content), FRASE)

    def test_lleva_sus_pacientes_y_toda_su_historia(self):
        p = self.copia(self.u_ana)
        self.assertEqual(cedulas(p), {"111", "222"})
        notas = {r["fields"]["notes"] for r in p["records"] if r["model"] == "clinical.evolution"}
        self.assertEqual(notas, {"Control", "Interconsulta"})
        self.assertIn("patients.medicalbackground", modelos(p))
        self.assertEqual(p["manifest"]["alcance"]["tipo"], "profesional")
        self.assertEqual(p["manifest"]["alcance"]["pacientes"], 2)

    def test_no_lleva_lo_de_otros_ni_la_gestion_de_la_clinica(self):
        p = self.copia(self.u_ana)
        citas = [r for r in p["records"] if r["model"] == "agenda.appointment"]
        self.assertEqual([c["fields"]["doctor"] for c in citas], [str(self.ana.pk)])
        usuarios = [r for r in p["records"] if r["model"] == "accounts.user"]
        self.assertEqual([u["pk"] for u in usuarios], [str(self.u_ana.pk)])
        self.assertNotIn("password", usuarios[0]["fields"])
        self.assertFalse({m for m in modelos(p) if m.startswith(("billing.", "inventory.", "whatsapp."))})
        self.assertNotIn("accounts.auditlog", modelos(p))

    def test_el_colega_se_lleva_solo_lo_suyo(self):
        self.assertEqual(cedulas(self.copia(self.u_luis)), {"111", "333"})

    def test_auxiliar_sin_pacientes_obtiene_una_copia_vacia_de_pacientes(self):
        p = self.copia(self.auxiliar)
        self.assertEqual(cedulas(p), set())
        self.assertEqual(p["manifest"]["alcance"]["pacientes"], 0)

    def test_la_administracion_se_lleva_la_clinica_entera(self):
        p = self.copia(self.admin)
        self.assertEqual(cedulas(p), {"111", "222", "333"})
        self.assertIn("accounts.auditlog", modelos(p))

    def test_sin_la_funcion_no_hay_copia(self):
        self.u_ana.funciones = {"respaldo": False}
        self.u_ana.save()
        self.client.force_authenticate(user=self.u_ana)
        self.assertEqual(self.client.post(self.url, {"passphrase": FRASE}).status_code, 403)

    def test_recepcion_no_aunque_se_la_marquen(self):
        """«Respaldo» no aplica a recepción: no ve datos clínicos."""
        self.recepcion.funciones = {"respaldo": True}
        self.recepcion.save()
        self.client.force_authenticate(user=self.recepcion)
        self.assertEqual(self.client.post(self.url, {"passphrase": FRASE}).status_code, 403)

    def test_cada_uno_abre_solo_las_suyas(self):
        de_ana = self.descargar(self.u_ana).content
        de_clinica = self.descargar(self.admin).content
        self.assertEqual(self.abrir(self.u_ana, de_ana, "a.zip").status_code, 200)
        self.assertEqual(self.abrir(self.u_luis, de_ana, "a.zip").status_code, 403)
        self.assertEqual(self.abrir(self.u_ana, de_clinica, "c.zip").status_code, 403)
        # La administración abre cualquiera de su clínica.
        self.assertEqual(self.abrir(self.admin, de_ana, "a.zip").status_code, 200)
        acciones = list(AuditLog.objects.filter(entity_type="TenantBackup").values_list("action", flat=True))
        self.assertIn("decrypt_backup_denied", acciones)


class CopiaDeLaClinica(Base):
    def test_incluye_la_app_y_los_logros(self):
        from apps.common.tenant_backup import _exportable_models

        etiquetas = {label for label, _, _ in _exportable_models()}
        self.assertTrue({"app_paciente.SolicitudCita", "app_paciente.MensajeConsultorio",
                         "logros.Logro", "logros.LogroDePaciente"} <= etiquetas)

    def test_no_lleva_el_token_de_whatsapp(self):
        from apps.whatsapp.models import ConfiguracionWhatsApp

        config = ConfiguracionWhatsApp(tenant=self.tenant, phone_number_id="123")
        config.token = "EAAG-secreto-de-meta"
        config.save()
        p = read_encrypted(build_encrypted(self.tenant, FRASE, self.admin)[0], FRASE)
        [fila] = [r for r in p["records"] if r["model"] == "whatsapp.configuracionwhatsapp"]
        self.assertNotIn("access_token_cifrado", fila["fields"])
        self.assertEqual(fila["fields"]["phone_number_id"], "123")


class HerramientaDeTerminal(SimpleTestCase):
    """descifrar.py abre, sin nada de este proyecto, lo que genera el servidor."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from apps.common.tenant_backup import encrypt

        contenido = {"manifest": {"format": "clinica-backup", "version": 1, "total_records": 2,
                                  "generated_at": "2026-09-30T10:00:00-05:00",
                                  "tenant": {"name": "Clínica Sonrisa"}},
                     "records": [{"model": "patients.patient", "pk": "a", "fields": {"first_name": "Ñandú; «x»"}},
                                 {"model": "clinical.evolution", "pk": "b", "fields": {"notes": "Línea 1\nLínea 2"}}]}
        import gzip

        cls.contenido = contenido
        cls.blob = encrypt(gzip.compress(json.dumps(contenido).encode()), FRASE)
        cls.dir = tempfile.TemporaryDirectory()
        cls.ruta = Path(cls.dir.name)
        (cls.ruta / "copia.clinicabk").write_bytes(cls.blob)
        (cls.ruta / "copia.zip").write_bytes(empaquetar(cls.blob, "copia.clinicabk", contenido["manifest"]))

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()
        super().tearDownClass()

    def ejecutar(self, *args, frase=FRASE):
        # Se ejecuta aparte y desde fuera del proyecto: no puede apoyarse
        # en nada de Django ni de este repositorio.
        entorno = {**os.environ, "FRASE_RESPALDO": frase}
        entorno.pop("DJANGO_SETTINGS_MODULE", None)
        return subprocess.run([sys.executable, str(DESCIFRAR_PY), *args], cwd=self.ruta,
                              env=entorno, capture_output=True, text=True, timeout=60)

    def test_abre_la_copia_y_escribe_json_y_csv(self):
        r = self.ejecutar("copia.clinicabk", "--csv", "tablas")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads((self.ruta / "copia.json").read_text("utf-8")), self.contenido)
        csv = (self.ruta / "tablas" / "patients.patient.csv").read_bytes()
        self.assertTrue(csv.startswith(b"\xef\xbb\xbf"))           # BOM: Excel lo abre en UTF-8
        self.assertIn('a;"Ñandú; «x»"', csv.decode("utf-8-sig"))
        self.assertIn("SIN CIFRAR", r.stdout)

    def test_abre_el_zip_tal_cual(self):
        r = self.ejecutar("copia.zip", "--salida", "desde-zip.json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads((self.ruta / "desde-zip.json").read_text("utf-8")), self.contenido)

    def test_frase_equivocada(self):
        r = self.ejecutar("copia.clinicabk", "--salida", "no.json", frase="otra-frase-cualquiera")
        self.assertEqual(r.returncode, 1)
        self.assertIn("la frase no es la correcta", r.stderr)
        self.assertFalse((self.ruta / "no.json").exists())

    def test_el_zip_de_herramientas_no_confunde_al_panel(self):
        with self.assertRaises(BackupError):
            from apps.common.paquete_respaldo import solo_herramientas

            sacar_copia(solo_herramientas())
