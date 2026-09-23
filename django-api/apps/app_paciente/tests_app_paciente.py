"""
La API de la app del paciente (Sprint 89).

Aquí lo que se prueba no es sobre todo que los datos salgan, sino que
salgan LOS SUYOS Y SOLO LOS SUYOS. Es una aplicación instalada en un
teléfono, con datos de salud, y el token de sesión de un paciente es lo
más fácil de obtener de todo el sistema.

Las cuatro mitades:

  1. Que el paciente vea lo suyo.
  2. Que NO vea lo de otro paciente, ni siquiera pidiéndolo.
  3. Que no vea lo que el profesional no marcó como visible.
  4. Que el personal de la clínica no entre por esta puerta, ni el
     paciente por la del panel.
"""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.agenda.models import Appointment, Doctor
from apps.billing.models import Budget, Installment, PaymentPlan
from apps.clinical.models import Evolution
from apps.common.models import Tenant
from apps.patients.models import Patient


class BaseApp(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica App", ruc="1790000089001")
        du = User.objects.create_user(
            email="doc@app.ec", password="superseguro123", role="doctor",
            tenant=self.tenant, full_name="Dra. Elena Ruiz",
        )
        self.doctor = Doctor.objects.create(tenant=self.tenant, user=du)

        self.ana_user = User.objects.create_user(
            email="ana@app.ec", password="superseguro123", role="patient",
            tenant=self.tenant, full_name="Ana Vega",
        )
        self.ana = Patient.objects.create(
            tenant=self.tenant, first_name="Ana", last_name="Vega",
            national_id="0102030401", user=self.ana_user,
        )
        self.otro_user = User.objects.create_user(
            email="beto@app.ec", password="superseguro123", role="patient",
            tenant=self.tenant, full_name="Beto Lara",
        )
        self.otro = Patient.objects.create(
            tenant=self.tenant, first_name="Beto", last_name="Lara",
            national_id="0102030402", user=self.otro_user,
        )

    def como_ana(self):
        self.client.force_authenticate(user=self.ana_user)

    def _cita(self, ficha, dentro_de_dias=3, estado="confirmed"):
        inicio = timezone.now() + timedelta(days=dentro_de_dias)
        return Appointment.objects.create(
            tenant=self.tenant, patient=ficha, doctor=self.doctor,
            scheduled_start=inicio, scheduled_end=inicio + timedelta(minutes=30),
            status=estado, notes="Nota interna que el paciente NO debe leer",
        )

    def _cuota(self, ficha, dias, monto="100.00", estado="pending"):
        presupuesto = Budget.objects.create(
            tenant=self.tenant, patient=ficha, total_amount=Decimal(monto),
        )
        plan = PaymentPlan.objects.create(
            tenant=self.tenant, budget=presupuesto, patient=ficha,
            total_amount=Decimal(monto), installment_count=1,
        )
        return Installment.objects.create(
            tenant=self.tenant, payment_plan=plan, patient=ficha, number=1,
            due_date=timezone.localdate() + timedelta(days=dias),
            amount=Decimal(monto), status=estado,
        )


class ElPacienteVeLoSuyoTests(BaseApp):
    def test_su_perfil_resume_lo_que_le_importa(self):
        self._cita(self.ana)
        self._cuota(self.ana, dias=-10)          # vencida
        self._cuota(self.ana, dias=20)           # por vencer
        self.como_ana()
        r = self.client.get("/api/v1/app/me/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["nombre"], "Ana Vega")
        self.assertEqual(r.data["clinica"], "Clínica App")
        self.assertEqual(r.data["cuotas_pendientes"], 2)
        self.assertEqual(r.data["cuotas_vencidas"], 1)
        self.assertIsNotNone(r.data["proxima_cita"])

    def test_sus_citas_separan_proximas_de_anteriores(self):
        self._cita(self.ana, dentro_de_dias=5)
        self._cita(self.ana, dentro_de_dias=-20)
        self.como_ana()
        r = self.client.get("/api/v1/app/citas/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data["proximas"]), 1)
        self.assertEqual(len(r.data["anteriores"]), 1)

    def test_una_cita_no_lleva_las_notas_internas(self):
        """
        El campo `notes` de una cita es para la clínica. Que viaje al
        teléfono por ir «de paso» en el serializador sería una fuga.
        """
        self._cita(self.ana)
        self.como_ana()
        completo = str(self.client.get("/api/v1/app/citas/").data)
        self.assertNotIn("Nota interna", completo)

    def test_su_saldo_lista_las_cuotas_con_su_vencimiento(self):
        self._cuota(self.ana, dias=-5, monto="80.00")
        self.como_ana()
        r = self.client.get("/api/v1/app/saldo/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["saldo_total"], "80.00")
        self.assertEqual(len(r.data["cuotas"]), 1)
        self.assertTrue(r.data["cuotas"][0]["vencida"])


class SoloLoQueElProfesionalDecidioMostrarTests(BaseApp):
    def test_una_receta_marcada_visible_llega_a_la_app(self):
        Evolution.objects.create(
            tenant=self.tenant, patient=self.ana, doctor=self.doctor,
            type=Evolution.Type.PRESCRIPTION, date=timezone.localdate(),
            notes="Amoxicilina 500 mg cada 8 horas", visible_to_patient=True,
        )
        self.como_ana()
        r = self.client.get("/api/v1/app/indicaciones/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data), 1)
        self.assertIn("Amoxicilina", r.data[0]["texto"])

    def test_una_nota_clinica_NO_llega_aunque_este_marcada(self):
        """
        Lista blanca de tipos, no exclusión: si mañana alguien marca por
        error una nota clínica como visible, la app no la publica.
        """
        Evolution.objects.create(
            tenant=self.tenant, patient=self.ana, doctor=self.doctor,
            type=Evolution.Type.CLINICAL_NOTE, date=timezone.localdate(),
            notes="Sospecha de lesión a descartar", visible_to_patient=True,
        )
        self.como_ana()
        r = self.client.get("/api/v1/app/indicaciones/")
        self.assertEqual(r.data, [])

    def test_una_receta_sin_marcar_no_llega(self):
        Evolution.objects.create(
            tenant=self.tenant, patient=self.ana, doctor=self.doctor,
            type=Evolution.Type.PRESCRIPTION, date=timezone.localdate(),
            notes="Borrador de receta", visible_to_patient=False,
        )
        self.como_ana()
        self.assertEqual(self.client.get("/api/v1/app/indicaciones/").data, [])


class NuncaLosDatosDeOtroPacienteTests(BaseApp):
    """La mitad que de verdad importa."""

    def test_las_citas_de_otro_no_aparecen(self):
        self._cita(self.otro)
        self.como_ana()
        r = self.client.get("/api/v1/app/citas/")
        self.assertEqual(r.data["proximas"], [])
        self.assertEqual(r.data["anteriores"], [])

    def test_el_saldo_de_otro_no_aparece(self):
        self._cuota(self.otro, dias=5, monto="999.00")
        self.como_ana()
        r = self.client.get("/api/v1/app/saldo/")
        self.assertEqual(r.data["saldo_total"], "0")
        self.assertEqual(r.data["cuotas"], [])

    def test_las_recetas_de_otro_no_aparecen(self):
        Evolution.objects.create(
            tenant=self.tenant, patient=self.otro, doctor=self.doctor,
            type=Evolution.Type.PRESCRIPTION, date=timezone.localdate(),
            notes="Receta de Beto", visible_to_patient=True,
        )
        self.como_ana()
        self.assertEqual(self.client.get("/api/v1/app/indicaciones/").data, [])

    def test_no_sirve_de_nada_pedir_otro_paciente(self):
        """
        No hay parámetro de paciente en ninguna ruta, y mandarlo tampoco
        cambia nada: la ficha sale del token. Se comprueba porque un
        endpoint que aceptara ese parámetro sería una invitación.
        """
        self._cita(self.otro)
        self.como_ana()
        for consulta in (f"?patient={self.otro.id}", f"?paciente={self.otro.id}",
                         f"?patient_id={self.otro.id}", f"?id={self.otro.id}"):
            r = self.client.get(f"/api/v1/app/citas/{consulta}")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.data["proximas"], [], f"se coló con {consulta}")


class CadaUnoPorSuPuertaTests(BaseApp):
    def test_el_personal_no_entra_por_la_app(self):
        admin = User.objects.create_user(
            email="admin@app.ec", password="superseguro123", role="admin",
            tenant=self.tenant,
        )
        self.client.force_authenticate(user=admin)
        for ruta in ("/api/v1/app/me/", "/api/v1/app/citas/",
                     "/api/v1/app/saldo/", "/api/v1/app/indicaciones/"):
            self.assertEqual(self.client.get(ruta).status_code, 403, ruta)

    def test_sin_autenticar_no_se_ve_nada(self):
        self.assertIn(self.client.get("/api/v1/app/me/").status_code, (401, 403))

    def test_un_paciente_sin_ficha_recibe_una_explicacion_no_una_lista_vacia(self):
        """
        Decirle «no tienes citas» a alguien cuya cuenta no está enlazada
        es mentirle: no es que no tenga, es que no lo estamos encontrando.
        """
        suelto = User.objects.create_user(
            email="suelto@app.ec", password="superseguro123", role="patient",
            tenant=self.tenant,
        )
        self.client.force_authenticate(user=suelto)
        r = self.client.get("/api/v1/app/citas/")
        self.assertEqual(r.status_code, 403)
        self.assertIn("recepción", str(r.data).lower())


class LaMarcaDeLaClinicaTests(APITestCase):
    """
    La app se pinta con los colores, el nombre y el logotipo de SU
    clínica. Lo que se comprueba aquí es que no se vea la de otra, y que
    los colores lleguen resueltos para que la app no tenga que saber
    nada de temas.
    """

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.tenant = Tenant.objects.create(name="Clínica Marca", ruc="1790000094001")
        self.paciente = Patient.objects.create(
            tenant=self.tenant, first_name="Ana", last_name="Marca",
            national_id="1700000200")
        self.usuario = User.objects.create_user(
            phone="+593999000200", role="patient", full_name="Ana Marca",
            tenant=self.tenant)
        self.paciente.user = self.usuario
        self.paciente.save()
        self.client.force_authenticate(user=self.usuario)

    def _marca(self, **kwargs):
        from apps.configuration.models import ClinicBranding
        return ClinicBranding.objects.create(tenant=self.tenant, **kwargs)

    def test_sin_personalizar_se_usa_el_nombre_del_tenant(self):
        r = self.client.get("/api/v1/app/clinica/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["nombre"], "Clínica Marca")
        self.assertEqual(r.data["color_principal"], "#14639e")
        self.assertIsNone(r.data["logo"])

    def test_el_nombre_comercial_manda_sobre_el_del_tenant(self):
        self._marca(display_name="Sonrisa Feliz")
        r = self.client.get("/api/v1/app/clinica/")
        self.assertEqual(r.data["nombre"], "Sonrisa Feliz")

    def test_los_colores_llegan_resueltos_y_no_el_nombre_del_tema(self):
        # Si llegara «petroleo», la app necesitaría su propia tabla y se
        # desincronizaría con el panel.
        self._marca(theme={"preset": "petroleo", "primary": "", "secondary": ""})
        r = self.client.get("/api/v1/app/clinica/")
        self.assertEqual(r.data["color_principal"], "#0e5c63")
        self.assertEqual(r.data["color_secundario"], "#9fe1cb")

    def test_un_color_invalido_no_llega_a_pintar_la_app(self):
        self._marca(theme={"preset": "custom", "primary": "azulito", "secondary": ""})
        r = self.client.get("/api/v1/app/clinica/")
        self.assertEqual(r.data["color_principal"], "#14639e")

    def test_se_devuelve_el_telefono_para_poder_llamar(self):
        self._marca(phone="02 244 8890")
        r = self.client.get("/api/v1/app/clinica/")
        self.assertEqual(r.data["telefono"], "02 244 8890")

    def test_nunca_se_ve_la_marca_de_otra_clinica(self):
        otra = Tenant.objects.create(name="Otra Clínica", ruc="1790000094099")
        from apps.configuration.models import ClinicBranding
        ClinicBranding.objects.create(tenant=otra, display_name="La De Al Lado")
        r = self.client.get("/api/v1/app/clinica/")
        self.assertEqual(r.data["nombre"], "Clínica Marca")

    def test_una_cuenta_sin_ficha_no_pasa_ni_a_la_parte_decorativa(self):
        self.paciente.user = None
        self.paciente.save()
        r = self.client.get("/api/v1/app/clinica/")
        self.assertEqual(r.status_code, 403)
