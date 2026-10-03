"""
Los recordatorios salen desde la cuenta de WhatsApp de CADA clínica.

Antes todos salían desde la cuenta de la plataforma, la de las
variables de entorno. Con una sola clínica daba igual; con varias, el
paciente de la clínica A recibía un mensaje desde un número que no
conocía, firmado como si fuera su clínica.

Lo que se fija aquí:

  - que en la petición al gateway viajen las credenciales de la clínica
    de esa cita, y no las de otra;
  - que una clínica sin cuenta lista NO envíe, en vez de caer a la de
    la plataforma;
  - que en ese caso la cita no quede marcada como recordada, para que
    el recordatorio salga el día que conecte su cuenta;
  - que quitarle la funcionalidad pare los envíos aunque la cuenta siga
    conectada.
"""

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.agenda.models import Appointment, Doctor
from apps.common.funcionalidades import normalizar
from apps.common.models import Tenant
from apps.configuration.models import SystemParameter
from apps.patients.models import Patient
from apps.whatsapp.models import WhatsAppOptIn
from apps.whatsapp.tasks import notify_doctor_patient_arrived, send_appointment_reminders
from apps.whatsapp.tests import conectar_whatsapp


class _Respuesta:
    @staticmethod
    def raise_for_status():
        return None

    @staticmethod
    def json():
        return {"status": "queued", "provider_message_id": "wamid.X"}


class EnvioPorClinicaTests(TestCase):
    def setUp(self):
        self.enviados = []
        parche = mock.patch(
            "apps.whatsapp.gateway_client.httpx.post",
            side_effect=lambda url, json=None, **kw: self.enviados.append(json) or _Respuesta(),
        )
        parche.start()
        self.addCleanup(parche.stop)

    def clinica(self, nombre, ruc, telefono):
        tenant = Tenant.objects.create(name=nombre, ruc=ruc)
        SystemParameter.objects.create(tenant=tenant, key="ventana_recordatorio_horas", value="24")
        doc = User.objects.create_user(email=f"doc@{ruc}.ec", password="superseguro123",
                                       role="doctor", tenant=tenant, phone="+59398" + ruc[-7:])
        doctor = Doctor.objects.create(tenant=tenant, user=doc)
        paciente = Patient.objects.create(tenant=tenant, first_name="Ana", last_name="Paz",
                                          national_id=ruc[:10], phone=telefono)
        WhatsAppOptIn.objects.create(tenant=tenant, patient=paciente)
        cita = Appointment.objects.create(
            tenant=tenant, patient=paciente, doctor=doctor,
            scheduled_start=timezone.now() + timedelta(hours=6),
            scheduled_end=timezone.now() + timedelta(hours=6, minutes=30),
            status="confirmed",
        )
        return tenant, cita

    def test_cada_recordatorio_lleva_las_credenciales_de_su_clinica(self):
        a, _ = self.clinica("Clínica A", "1790000097001", "+593999000001")
        b, _ = self.clinica("Clínica B", "1790000097002", "+593999000002")
        for tenant, numero, plantilla in ((a, "NUM_A", "recordatorio_cita"),
                                          (b, "NUM_B", "aviso_de_b")):
            config = conectar_whatsapp(tenant, plantilla=plantilla)
            config.phone_number_id = numero
            config.save(update_fields=["phone_number_id"])

        self.assertEqual(send_appointment_reminders()["reminders_sent"], 2)

        por_telefono = {p["to_phone"]: p for p in self.enviados}
        self.assertEqual(por_telefono["+593999000001"]["credenciales"]["phone_number_id"], "NUM_A")
        self.assertEqual(por_telefono["+593999000002"]["credenciales"]["phone_number_id"], "NUM_B")
        # Y con la plantilla que cada una tiene aprobada en su cuenta.
        self.assertEqual(por_telefono["+593999000001"]["template_name"], "recordatorio_cita")
        self.assertEqual(por_telefono["+593999000002"]["template_name"], "aviso_de_b")

    def test_sin_cuenta_lista_no_se_envia_ni_se_marca(self):
        _, cita = self.clinica("Clínica Sin", "1790000097003", "+593999000003")

        self.assertEqual(send_appointment_reminders()["reminders_sent"], 0)
        self.assertEqual(self.enviados, [], "salió por la cuenta de la plataforma")
        cita.refresh_from_db()
        self.assertIsNone(cita.reminder_sent_at)

        # El día que conecta su cuenta, el recordatorio sale.
        conectar_whatsapp(cita.tenant)
        self.assertEqual(send_appointment_reminders()["reminders_sent"], 1)

    def test_sin_la_funcionalidad_contratada_no_se_envia(self):
        tenant, _ = self.clinica("Clínica Baja", "1790000097004", "+593999000004")
        conectar_whatsapp(tenant)
        tenant.funcionalidades = normalizar({"whatsapp": False})
        tenant.save(update_fields=["funcionalidades"])

        self.assertEqual(send_appointment_reminders()["reminders_sent"], 0)
        self.assertEqual(self.enviados, [])

    def test_el_aviso_al_doctor_tambien_sale_de_la_clinica(self):
        tenant, cita = self.clinica("Clínica D", "1790000097005", "+593999000005")

        self.assertEqual(notify_doctor_patient_arrived(cita.id)["sent"], False)
        self.assertEqual(self.enviados, [])

        conectar_whatsapp(tenant)
        self.assertTrue(notify_doctor_patient_arrived(cita.id)["sent"])
        self.assertEqual(self.enviados[0]["credenciales"]["phone_number_id"], "555000111")
