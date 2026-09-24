"""
Pedir cita y escribir al consultorio desde la app, y su bandeja.

Lo que se fija:
  - el paciente solo ve y crea lo SUYO, sin identificador en la petición;
  - agendar crea una cita real, con las validaciones de la agenda, y la
    solicitud no queda «agendada» si la cita no se pudo crear;
  - un rechazo lleva siempre explicación;
  - los límites que impiden inundar la bandeja desde un teléfono;
  - quién puede hacer qué en el panel;
  - la clínica sin la app contratada no expone nada de esto.
"""

from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.agenda.models import Appointment, Doctor
from apps.app_paciente.models import MensajeConsultorio, SolicitudCita
from apps.common.funcionalidades import normalizar
from apps.common.models import Tenant
from apps.patients.models import Patient


class Base(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Contacto", ruc="1790000099001")
        self.recepcion = User.objects.create_user(
            email="rec@contacto.ec", password="clave-larga-8gatos", role="reception", tenant=self.tenant)
        du = User.objects.create_user(
            email="doc@contacto.ec", password="clave-larga-8gatos", role="doctor",
            tenant=self.tenant, full_name="Dra. Paz")
        self.doctor_user = du
        self.doctor = Doctor.objects.create(tenant=self.tenant, user=du)
        self.ana_user = User.objects.create_user(
            email="ana@contacto.ec", password="clave-larga-8gatos", role="patient", tenant=self.tenant)
        self.ana = Patient.objects.create(tenant=self.tenant, first_name="Ana", last_name="Vega",
                                          national_id="0102030501", user=self.ana_user)
        self.beto_user = User.objects.create_user(
            email="beto@contacto.ec", password="clave-larga-8gatos", role="patient", tenant=self.tenant)
        self.beto = Patient.objects.create(tenant=self.tenant, first_name="Beto", last_name="Lara",
                                           national_id="0102030502", user=self.beto_user)

    def manana(self, dias=1):
        return (timezone.localdate() + timedelta(days=dias)).isoformat()


class PacientePideCitaTests(Base):
    def test_pide_cita_y_la_ve_pendiente(self):
        self.client.force_authenticate(self.ana_user)
        r = self.client.post("/api/v1/app/solicitudes-cita/",
                             {"fecha_preferida": self.manana(), "franja": "manana", "motivo": "Me duele una muela"},
                             format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["estado"], "pendiente")
        lista = self.client.get("/api/v1/app/solicitudes-cita/").data
        self.assertEqual(len(lista), 1)
        self.assertEqual(lista[0]["motivo"], "Me duele una muela")

    def test_no_ve_las_de_otro(self):
        SolicitudCita.objects.create(tenant=self.tenant, patient=self.beto,
                                     fecha_preferida=timezone.localdate() + timedelta(days=2))
        self.client.force_authenticate(self.ana_user)
        self.assertEqual(self.client.get("/api/v1/app/solicitudes-cita/").data, [])

    def test_fecha_pasada_o_demasiado_lejana(self):
        self.client.force_authenticate(self.ana_user)
        ayer = (timezone.localdate() - timedelta(days=1)).isoformat()
        self.assertEqual(self.client.post("/api/v1/app/solicitudes-cita/",
                                          {"fecha_preferida": ayer}, format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/v1/app/solicitudes-cita/",
                                          {"fecha_preferida": self.manana(400)}, format="json").status_code, 400)

    def test_como_mucho_tres_pendientes(self):
        self.client.force_authenticate(self.ana_user)
        for i in range(3):
            r = self.client.post("/api/v1/app/solicitudes-cita/", {"fecha_preferida": self.manana(i + 1)},
                                 format="json")
            self.assertEqual(r.status_code, 201)
        r = self.client.post("/api/v1/app/solicitudes-cita/", {"fecha_preferida": self.manana(5)}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_el_personal_no_usa_el_lado_del_paciente(self):
        self.client.force_authenticate(self.recepcion)
        self.assertEqual(self.client.get("/api/v1/app/solicitudes-cita/").status_code, 403)

    def test_sin_la_app_contratada_no_hay_nada(self):
        self.tenant.funcionalidades = normalizar({"app_paciente": False})
        self.tenant.save(update_fields=["funcionalidades"])
        self.client.force_authenticate(self.ana_user)
        self.assertEqual(self.client.get("/api/v1/app/solicitudes-cita/").status_code, 403)
        self.client.force_authenticate(self.recepcion)
        self.assertEqual(self.client.get("/api/v1/bandeja-app/resumen/").status_code, 403)


class RecepcionAtiendeTests(Base):
    def setUp(self):
        super().setUp()
        self.sol = SolicitudCita.objects.create(
            tenant=self.tenant, patient=self.ana, motivo="Limpieza",
            fecha_preferida=timezone.localdate() + timedelta(days=3))

    def _hueco(self, dias=3, hora=10):
        inicio = (timezone.now() + timedelta(days=dias)).replace(hour=hora, minute=0, second=0, microsecond=0)
        return inicio, inicio + timedelta(minutes=30)

    def test_agendar_crea_la_cita_y_el_paciente_lo_ve(self):
        self.client.force_authenticate(self.recepcion)
        inicio, fin = self._hueco()
        r = self.client.post(f"/api/v1/bandeja-app/solicitudes/{self.sol.id}/agendar/", {
            "doctor": str(self.doctor.id), "scheduled_start": inicio.isoformat(),
            "scheduled_end": fin.isoformat(),
        }, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        cita = Appointment.objects.get(patient=self.ana)
        self.assertIn("Limpieza", cita.notes)
        self.client.force_authenticate(self.ana_user)
        mia = self.client.get("/api/v1/app/solicitudes-cita/").data[0]
        self.assertEqual(mia["estado"], "agendada")
        self.assertEqual(mia["cita"]["id"], str(cita.id))

    def test_si_la_cita_no_vale_la_solicitud_sigue_pendiente(self):
        """Encima de otra cita del doctor: ni cita nueva ni solicitud marcada."""
        inicio, fin = self._hueco()
        Appointment.objects.create(tenant=self.tenant, patient=self.beto, doctor=self.doctor,
                                   scheduled_start=inicio, scheduled_end=fin, status="confirmed")
        self.client.force_authenticate(self.recepcion)
        r = self.client.post(f"/api/v1/bandeja-app/solicitudes/{self.sol.id}/agendar/", {
            "doctor": str(self.doctor.id), "scheduled_start": inicio.isoformat(),
            "scheduled_end": fin.isoformat(),
        }, format="json")
        self.assertEqual(r.status_code, 400)
        self.sol.refresh_from_db()
        self.assertEqual(self.sol.estado, "pendiente")
        self.assertFalse(Appointment.objects.filter(patient=self.ana).exists())

    def test_no_se_atiende_dos_veces(self):
        self.client.force_authenticate(self.recepcion)
        self.client.post(f"/api/v1/bandeja-app/solicitudes/{self.sol.id}/rechazar/",
                         {"respuesta": "Esa semana no hay agenda"}, format="json")
        r = self.client.post(f"/api/v1/bandeja-app/solicitudes/{self.sol.id}/rechazar/",
                             {"respuesta": "otra vez"}, format="json")
        self.assertEqual(r.status_code, 409)

    def test_rechazar_exige_explicacion(self):
        self.client.force_authenticate(self.recepcion)
        r = self.client.post(f"/api/v1/bandeja-app/solicitudes/{self.sol.id}/rechazar/", {}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.post(f"/api/v1/bandeja-app/solicitudes/{self.sol.id}/rechazar/",
                             {"respuesta": "Llámanos para buscar otro día"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["estado"], "rechazada")

    def test_un_doctor_ve_pero_no_agenda(self):
        self.client.force_authenticate(self.doctor_user)
        self.assertEqual(self.client.get("/api/v1/bandeja-app/solicitudes/").status_code, 200)
        r = self.client.post(f"/api/v1/bandeja-app/solicitudes/{self.sol.id}/rechazar/",
                             {"respuesta": "no"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_otra_clinica_no_la_ve(self):
        otra = Tenant.objects.create(name="Otra", ruc="1790000099002")
        ajena = User.objects.create_user(email="rec@otra.ec", password="clave-larga-8gatos",
                                         role="reception", tenant=otra)
        self.client.force_authenticate(ajena)
        self.assertEqual(self.client.get("/api/v1/bandeja-app/solicitudes/").data, [])
        r = self.client.post(f"/api/v1/bandeja-app/solicitudes/{self.sol.id}/rechazar/",
                             {"respuesta": "x"}, format="json")
        self.assertEqual(r.status_code, 404)

    def test_resumen_cuenta_lo_pendiente(self):
        MensajeConsultorio.objects.create(tenant=self.tenant, patient=self.ana, texto="Hola")
        self.client.force_authenticate(self.recepcion)
        r = self.client.get("/api/v1/bandeja-app/resumen/")
        self.assertEqual(r.data, {"solicitudes_pendientes": 1, "mensajes_sin_responder": 1})


class MensajesTests(Base):
    def test_pregunta_y_respuesta(self):
        self.client.force_authenticate(self.ana_user)
        r = self.client.post("/api/v1/app/mensajes/", {"texto": "¿Puedo comer después de la limpieza?"},
                             format="json")
        self.assertEqual(r.status_code, 201)
        self.client.force_authenticate(self.doctor_user)
        pendientes = self.client.get("/api/v1/bandeja-app/mensajes/").data
        self.assertEqual(len(pendientes), 1)
        r = self.client.post(f"/api/v1/bandeja-app/mensajes/{pendientes[0]['id']}/responder/",
                             {"respuesta": "Sí, a partir de una hora."}, format="json")
        self.assertEqual(r.status_code, 200)
        self.client.force_authenticate(self.ana_user)
        mio = self.client.get("/api/v1/app/mensajes/").data[0]
        self.assertEqual(mio["respuesta"], "Sí, a partir de una hora.")

    def test_mensaje_vacio_o_demasiado_largo(self):
        self.client.force_authenticate(self.ana_user)
        self.assertEqual(self.client.post("/api/v1/app/mensajes/", {"texto": "   "},
                                          format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/v1/app/mensajes/", {"texto": "x" * 1001},
                                          format="json").status_code, 400)

    def test_como_mucho_cinco_sin_responder(self):
        self.client.force_authenticate(self.ana_user)
        for i in range(5):
            self.assertEqual(self.client.post("/api/v1/app/mensajes/", {"texto": f"m{i}"},
                                              format="json").status_code, 201)
        self.assertEqual(self.client.post("/api/v1/app/mensajes/", {"texto": "m6"},
                                          format="json").status_code, 400)

    def test_un_auxiliar_lee_pero_no_responde(self):
        m = MensajeConsultorio.objects.create(tenant=self.tenant, patient=self.ana, texto="Hola")
        aux = User.objects.create_user(email="aux@contacto.ec", password="clave-larga-8gatos",
                                       role="auxiliary", tenant=self.tenant)
        self.client.force_authenticate(aux)
        self.assertEqual(self.client.get("/api/v1/bandeja-app/mensajes/").status_code, 200)
        r = self.client.post(f"/api/v1/bandeja-app/mensajes/{m.id}/responder/", {"respuesta": "x"},
                             format="json")
        self.assertEqual(r.status_code, 403)
