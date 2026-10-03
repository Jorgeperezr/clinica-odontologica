"""
Funciones de cada profesional (apps/accounts/funciones.py).

Lo que se fija, y por qué importa cada cosa:
  - quien ya existía conserva EXACTAMENTE el acceso de su rol: actualizar
    no puede quitarle el cobro a una recepcionista ni dárselo a un doctor;
  - al dar de alta se guardan las sugeridas para el rol, o las elegidas;
  - las funciones las comprueba la API, no solo el menú;
  - una función de un módulo que la clínica no tiene no abre nada;
  - el administrador lo tiene todo, siempre.
"""

from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.funciones import funciones_de
from apps.accounts.models import User
from apps.agenda.models import Doctor
from apps.common.funcionalidades import normalizar
from apps.common.models import Tenant
from apps.patients.models import Patient


class Base(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Funciones", ruc="1790000100001")
        self.admin = User.objects.create_user(email="adm@fun.ec", password="clave-larga-8gatos",
                                              role="admin", tenant=self.tenant)
        self.paciente = Patient.objects.create(tenant=self.tenant, first_name="Ana", last_name="Paz",
                                               national_id="0102030601")

    def usuario(self, correo, rol, funciones=None):
        u = User.objects.create_user(email=correo, password="clave-larga-8gatos", role=rol,
                                     tenant=self.tenant)
        if funciones is not None:
            u.funciones = funciones
            u.save(update_fields=["funciones"])
        if rol == "doctor":
            Doctor.objects.create(tenant=self.tenant, user=u)
        return u

    def crear_cita(self, quien, doctor_user):
        self.client.force_authenticate(quien)
        inicio = timezone.now() + timedelta(days=2)
        return self.client.post("/api/v1/appointments/", {
            "patient": str(self.paciente.id), "doctor": str(Doctor.objects.get(user=doctor_user).id),
            "scheduled_start": inicio.isoformat(),
            "scheduled_end": (inicio + timedelta(minutes=30)).isoformat(),
        }, format="json")


class QuienYaExistiaNoCambiaTests(Base):
    def test_recepcion_antigua_agenda_y_cobra(self):
        rec = self.usuario("rec@fun.ec", "reception")        # sin nada guardado
        f = funciones_de(rec)
        self.assertTrue(f["agenda"] and f["cobros"] and f["mensajes_app"])
        self.assertFalse(f["reportes"] or f["inventario"] or f["logros"] or f["whatsapp"])
        doc = self.usuario("doc@fun.ec", "doctor")
        self.assertEqual(self.crear_cita(rec, doc).status_code, 201)

    def test_doctor_antiguo_sigue_sin_agendar(self):
        doc = self.usuario("doc@fun.ec", "doctor")
        self.assertFalse(funciones_de(doc)["agenda"])
        self.assertEqual(self.crear_cita(doc, doc).status_code, 403)

    def test_auxiliar_antiguo_tiene_inventario(self):
        aux = self.usuario("aux@fun.ec", "auxiliary")
        self.assertTrue(funciones_de(aux)["inventario"])


class AltaConFuncionesTests(Base):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.admin)

    def alta(self, **extra):
        return self.client.post("/api/v1/users/", {
            "email": "nueva@fun.ec", "full_name": "Dra. Nueva", "role": "doctor",
            "password": "clave-larga-8gatos", **extra}, format="json")

    def test_sin_elegir_se_guardan_las_sugeridas(self):
        r = self.alta()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["funciones"]["agenda"])
        self.assertTrue(r.data["funciones"]["logros"])
        self.assertFalse(r.data["funciones"]["cobros"])
        u = User.objects.get(email="nueva@fun.ec")
        # Guardadas completas: no depende de lo heredado del rol.
        self.assertEqual(set(u.funciones), set(funciones_de(u)))

    def test_se_respeta_lo_elegido(self):
        r = self.alta(funciones={"agenda": False, "cobros": True})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertFalse(r.data["funciones"]["agenda"])
        self.assertTrue(r.data["funciones"]["cobros"])

    def test_claves_o_valores_raros_se_rechazan(self):
        self.assertEqual(self.alta(funciones={"borrar_todo": True}).status_code, 400)
        self.assertEqual(self.alta(funciones={"agenda": "sí"}).status_code, 400)

    def test_editar_cambia_solo_lo_pedido(self):
        rec = self.usuario("rec@fun.ec", "reception")          # heredadas
        r = self.client.patch(f"/api/v1/users/{rec.id}/", {"funciones": {"cobros": False}}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data["funciones"]["cobros"])
        self.assertTrue(r.data["funciones"]["agenda"])           # intacta

    def test_catalogo_para_el_panel(self):
        r = self.client.get("/api/v1/users/funciones/")
        self.assertEqual(r.status_code, 200)
        agenda = next(f for f in r.data if f["clave"] == "agenda")
        self.assertEqual(agenda["al_crear"], {"reception": True, "doctor": True, "auxiliary": False})

    def test_solo_el_administrador_asigna(self):
        rec = self.usuario("rec@fun.ec", "reception")
        self.client.force_authenticate(rec)
        self.assertEqual(self.client.get("/api/v1/users/funciones/").status_code, 403)


class LaApiLasComprueba(Base):
    def test_doctor_con_agenda_agenda(self):
        doc = self.usuario("doc@fun.ec", "doctor", {"agenda": True})
        self.assertEqual(self.crear_cita(doc, doc).status_code, 201)

    def test_recepcion_sin_cobros_no_cobra(self):
        rec = self.usuario("rec@fun.ec", "reception", {"cobros": False})
        self.client.force_authenticate(rec)
        r = self.client.get(f"/api/v1/patients/{self.paciente.id}/payments/")
        self.assertEqual(r.status_code, 403)

    def test_reportes_se_pueden_dar_a_quien_no_es_admin(self):
        doc = self.usuario("doc@fun.ec", "doctor", {"reportes": True})
        self.client.force_authenticate(doc)
        self.assertEqual(self.client.get("/api/v1/reports/new-patients/").status_code, 200)
        otro = self.usuario("doc2@fun.ec", "doctor")
        self.client.force_authenticate(otro)
        self.assertEqual(self.client.get("/api/v1/reports/new-patients/").status_code, 403)

    def test_sin_el_modulo_contratado_la_funcion_no_abre(self):
        self.tenant.funcionalidades = normalizar({"inventario": False})
        self.tenant.save(update_fields=["funcionalidades"])
        aux = self.usuario("aux@fun.ec", "auxiliary", {"inventario": True})
        self.client.force_authenticate(aux)
        self.assertEqual(self.client.get("/api/v1/reports/inventory/").status_code, 403)

    def test_el_administrador_lo_tiene_todo(self):
        self.assertTrue(all(funciones_de(self.admin).values()))

    def test_auth_me_las_da_al_panel(self):
        doc = self.usuario("doc@fun.ec", "doctor", {"agenda": True})
        self.client.force_authenticate(doc)
        r = self.client.get("/api/v1/auth/me/")
        self.assertTrue(r.data["funciones"]["agenda"])
        self.assertFalse(r.data["funciones"]["cobros"])
