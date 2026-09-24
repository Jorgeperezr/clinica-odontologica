"""
Rachas y logros: que se premie lo que se dice premiar.

Un programa de fidelidad que premia mal es peor que no tenerlo: el
paciente que sí fue a sus citas ve que no le tocó, y el que faltó ve que
sí. Por eso las reglas se prueban con meses concretos y no con «hoy».
"""

from datetime import date, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.agenda.models import Appointment, Doctor
from apps.billing.models import Budget, Installment, PaymentPlan
from apps.common.models import Tenant
from apps.configuration.models import Specialty, Treatment
from apps.logros import reglas
from apps.logros.models import Logro, LogroDePaciente
from apps.logros.views import evaluar
from apps.patients.models import Patient

MES = date(2026, 5, 1)


class Base(APITestCase):
    def setUp(self):
        cache.clear()
        self.tenant = Tenant.objects.create(name="Clínica Logros", ruc="1790000093001")
        self.esp = Specialty.objects.create(tenant=self.tenant, name="General")
        self.tr = Treatment.objects.create(
            tenant=self.tenant, name="Profilaxis", specialty=self.esp,
            base_price=Decimal("35.00"))
        self.admin = User.objects.create_user(
            email="admin@logros.ec", password="clave-larga-8gatos",
            role="admin", tenant=self.tenant)
        self.doctor_user = User.objects.create_user(
            email="doc@logros.ec", password="clave-larga-8gatos",
            role="doctor", tenant=self.tenant)
        self.doctor = Doctor.objects.create(
            tenant=self.tenant, user=self.doctor_user, license_number="ODO-1")
        self.paciente = Patient.objects.create(
            tenant=self.tenant, first_name="Ana", last_name="Logro",
            national_id="1700000001")

    def cita(self, dia, estado):
        inicio = timezone.make_aware(
            timezone.datetime.combine(dia, timezone.datetime.min.time())
        ) + timedelta(hours=10)
        return Appointment.objects.create(
            tenant=self.tenant, patient=self.paciente, doctor=self.doctor,
            treatment=self.tr, scheduled_start=inicio,
            scheduled_end=inicio + timedelta(minutes=45), status=estado)

    def cuota(self, vence, estado="pending"):
        b = Budget.objects.create(tenant=self.tenant, patient=self.paciente, notes="x")
        plan = PaymentPlan.objects.create(
            tenant=self.tenant, budget=b, patient=self.paciente,
            total_amount=Decimal("60.00"), installment_count=1)
        return Installment.objects.create(
            tenant=self.tenant, payment_plan=plan, patient=self.paciente,
            number=1, due_date=vence, amount=Decimal("60.00"), status=estado)


class LaReglaDeAsistenciaTests(Base):
    def test_fue_a_su_cita_y_no_falto(self):
        self.cita(date(2026, 5, 12), "completed")
        self.assertTrue(reglas.asistio_a_sus_citas(self.paciente, MES))

    def test_una_falta_lo_estropea(self):
        self.cita(date(2026, 5, 12), "completed")
        self.cita(date(2026, 5, 20), "no_show")
        self.assertFalse(reglas.asistio_a_sus_citas(self.paciente, MES))

    def test_cancelar_tambien_cuenta_como_falta(self):
        self.cita(date(2026, 5, 12), "completed")
        self.cita(date(2026, 5, 20), "cancelled")
        self.assertFalse(reglas.asistio_a_sus_citas(self.paciente, MES))

    def test_no_ir_nunca_NO_se_premia(self):
        """
        Sin citas no hay logro. Si no, el programa premiaría a quien
        nunca pisa la clínica por encima de quien va cada mes.
        """
        self.assertFalse(reglas.asistio_a_sus_citas(self.paciente, MES))

    def test_lo_del_mes_de_al_lado_no_cuenta(self):
        self.cita(date(2026, 6, 3), "completed")
        self.assertFalse(reglas.asistio_a_sus_citas(self.paciente, MES))

    def test_el_ultimo_dia_del_mes_sigue_siendo_del_mes(self):
        self.cita(date(2026, 5, 31), "completed")
        self.assertTrue(reglas.asistio_a_sus_citas(self.paciente, MES))


class LaReglaDePagosTests(Base):
    def test_sin_cuotas_vencidas(self):
        self.cuota(date(2026, 6, 15))
        self.assertTrue(reglas.estuvo_al_dia(self.paciente, MES))

    def test_una_vencida_dentro_del_mes_lo_estropea(self):
        self.cuota(date(2026, 5, 10))
        self.assertFalse(reglas.estuvo_al_dia(self.paciente, MES))

    def test_se_mira_el_cierre_del_mes_y_no_hoy(self):
        """
        El logro de mayo no puede depender de lo que se deba en
        noviembre: si no, el historial cambiaría solo.
        """
        self.cuota(date(2026, 9, 10))
        self.assertTrue(reglas.estuvo_al_dia(self.paciente, MES))

    def test_pagada_no_cuenta_como_vencida(self):
        self.cuota(date(2026, 5, 10), estado="paid")
        self.assertTrue(reglas.estuvo_al_dia(self.paciente, MES))


class LaRachaTests(Base):
    def test_tres_meses_seguidos(self):
        for mes in (3, 4, 5):
            self.cita(date(2026, mes, 10), "completed")
        logro = Logro.objects.create(
            tenant=self.tenant, nombre="Constancia", regla="asistencia_mensual")
        self.assertEqual(reglas.racha_de(self.paciente, logro, MES), 3)

    def test_un_hueco_corta_la_racha(self):
        for mes in (3, 5):
            self.cita(date(2026, mes, 10), "completed")
        logro = Logro.objects.create(
            tenant=self.tenant, nombre="Constancia", regla="asistencia_mensual")
        self.assertEqual(reglas.racha_de(self.paciente, logro, MES), 1)

    def test_una_regla_que_siempre_se_cumple_no_gira_para_siempre(self):
        """
        «Sin cuotas vencidas» es cierto para un paciente que nunca debió
        nada, en todos los meses hacia atrás. Sin tope, el bucle llegaría
        al año 1.
        """
        logro = Logro.objects.create(
            tenant=self.tenant, nombre="Al día", regla="al_dia_pagos")
        self.assertEqual(reglas.racha_de(self.paciente, logro, MES), 120)


class EvaluarTests(Base):
    def test_concede_y_no_repite(self):
        self.cita(date(2026, 5, 12), "completed")
        Logro.objects.create(
            tenant=self.tenant, nombre="Puntual", regla="asistencia_mensual")
        self.assertEqual(evaluar(self.tenant, MES), 1)
        # Volver a pulsar el botón tiene que ser inofensivo.
        self.assertEqual(evaluar(self.tenant, MES), 0)
        self.assertEqual(LogroDePaciente.objects.count(), 1)

    def test_exige_la_racha_completa(self):
        self.cita(date(2026, 5, 12), "completed")
        Logro.objects.create(
            tenant=self.tenant, nombre="Tres meses",
            regla="asistencia_mensual", meses_requeridos=3)
        self.assertEqual(evaluar(self.tenant, MES), 0)
        for mes in (3, 4):
            self.cita(date(2026, mes, 10), "completed")
        self.assertEqual(evaluar(self.tenant, MES), 1)

    def test_los_manuales_no_los_toca(self):
        Logro.objects.create(tenant=self.tenant, nombre="A mano", regla="manual")
        self.assertEqual(evaluar(self.tenant, MES), 0)


class QuienPuedeOtorgarTests(Base):
    def setUp(self):
        super().setUp()
        self.logro = Logro.objects.create(
            tenant=self.tenant, nombre="Gracias", regla="manual",
            beneficio="10% en tu próxima limpieza")

    def entrar(self, usuario):
        r = self.client.post("/api/v1/auth/login/",
                             {"email": usuario.email, "password": "clave-larga-8gatos"},
                             format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")

    def test_el_administrador_siempre_puede(self):
        self.entrar(self.admin)
        r = self.client.post("/api/v1/logros/otorgar/",
                             {"logro": str(self.logro.id),
                              "patient": str(self.paciente.id)}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["otorgado_por_nombre"], self.admin.full_name)

    def test_un_doctor_sin_el_permiso_no(self):
        self.entrar(self.doctor_user)
        r = self.client.post("/api/v1/logros/otorgar/",
                             {"logro": str(self.logro.id),
                              "patient": str(self.paciente.id)}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_un_doctor_con_el_permiso_si(self):
        # Ahora es una función del profesional (apps/accounts/funciones.py).
        self.doctor_user.funciones = {"logros": True}
        self.doctor_user.save(update_fields=["funciones"])
        self.entrar(self.doctor_user)
        r = self.client.post("/api/v1/logros/otorgar/",
                             {"logro": str(self.logro.id),
                              "patient": str(self.paciente.id)}, format="json")
        self.assertEqual(r.status_code, 201, r.data)

    def test_no_se_puede_premiar_a_un_paciente_de_otra_clinica(self):
        otra = Tenant.objects.create(name="Otra Clínica", ruc="1790000093099")
        ajeno = Patient.objects.create(
            tenant=otra, first_name="Ajeno", last_name="X", national_id="1700000099")
        self.entrar(self.admin)
        r = self.client.post("/api/v1/logros/otorgar/",
                             {"logro": str(self.logro.id),
                              "patient": str(ajeno.id)}, format="json")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(LogroDePaciente.objects.count(), 0)


class BorrarUnLogroConcedidoTests(Base):
    def test_desactiva_en_vez_de_borrar(self):
        """
        Borrarlo reescribiría la historia de quien lo ganó.
        """
        logro = Logro.objects.create(tenant=self.tenant, nombre="Fiel", regla="manual")
        LogroDePaciente.objects.create(
            tenant=self.tenant, patient=self.paciente, logro=logro)
        r = self.client.post("/api/v1/auth/login/",
                             {"email": self.admin.email, "password": "clave-larga-8gatos"},
                             format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        resp = self.client.delete(f"/api/v1/logros/{logro.id}/")
        self.assertIn(resp.status_code, (200, 204))
        logro.refresh_from_db()
        self.assertFalse(logro.activo)
        self.assertEqual(LogroDePaciente.objects.count(), 1)
