"""
Alertas clínicas: reglas (sin base de datos) y endpoints.

Lo que más importa aquí es lo que NO debe pasar: que «Niega alergias»
dispare una alerta de alergia, o que recepción vea antecedentes médicos
por la puerta de atrás de las alertas.
"""

from datetime import date
from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from apps.accounts.models import AuditLog, User
from apps.clinical.alertas import alertas_de_antecedentes, revisar_receta
from apps.clinical.models import Form033Record
from apps.common.models import Tenant
from apps.patients.models import MedicalBackground, Patient


def fondo(alergias="", medicacion="", condiciones="", embarazada=None):
    return SimpleNamespace(allergies=alergias, medications=medicacion,
                           conditions=condiciones, is_pregnant=embarazada)


def claves(alertas):
    return {a["clave"] for a in alertas}


class ReglasDeAntecedentes(SimpleTestCase):
    def test_alergia_a_penicilina_cita_la_frase_de_origen(self):
        [a] = alertas_de_antecedentes(fondo(alergias="Alergia a la Penicilina en la infancia"))
        self.assertEqual(a["clave"], "alergia_penicilina")
        self.assertEqual(a["nivel"], "alto")
        self.assertEqual(a["fuente"], "Alergias: «Alergia a la Penicilina en la infancia»")

    def test_amoxicilina_como_alergia_tambien_es_penicilina(self):
        self.assertIn("alergia_penicilina", claves(alertas_de_antecedentes(fondo(alergias="amoxicilina"))))

    def test_las_negaciones_no_disparan(self):
        for texto in ("Niega alergias", "Sin alergia a la penicilina", "No refiere alergia a penicilina",
                      "Ninguna", "Descarta alergia a AINE"):
            with self.subTest(texto=texto):
                self.assertEqual(alertas_de_antecedentes(fondo(alergias=texto)), [])
        self.assertEqual(alertas_de_antecedentes(fondo(medicacion="No toma anticoagulantes")), [])

    def test_una_negacion_no_tapa_la_frase_siguiente(self):
        a = alertas_de_antecedentes(fondo(alergias="Niega alergia al látex. Alérgica al ibuprofeno"))
        self.assertEqual(claves(a), {"alergia_aine"})

    def test_sin_tildes_ni_mayusculas(self):
        self.assertIn("alergia_latex", claves(alertas_de_antecedentes(fondo(alergias="LÁTEX"))))
        self.assertIn("anticoagulado", claves(alertas_de_antecedentes(fondo(medicacion="Sintrom 4 mg"))))

    def test_medicacion_y_condiciones(self):
        a = alertas_de_antecedentes(fondo(
            medicacion="Ácido alendrónico semanal; metformina 850",
            condiciones="Hipertensión controlada. Prótesis valvular aórtica",
        ))
        self.assertEqual(claves(a), {"bifosfonatos", "diabetes", "cardiovascular", "endocarditis"})
        niveles = {x["clave"]: x["nivel"] for x in a}
        self.assertEqual(niveles["diabetes"], "medio")
        self.assertEqual(niveles["endocarditis"], "alto")

    def test_embarazo(self):
        [a] = alertas_de_antecedentes(fondo(embarazada=True))
        self.assertEqual((a["clave"], a["fuente"]), ("embarazo", "Antecedentes: embarazo"))

    def test_sin_antecedentes_no_hay_alertas(self):
        self.assertEqual(alertas_de_antecedentes(None), [])
        self.assertEqual(alertas_de_antecedentes(fondo()), [])

    def test_casillas_del_formulario_033(self):
        f033 = SimpleNamespace(embarazada=True, antecedentes_personales={
            "Alergia antibiótico": {"checked": True, "detail": ""},
            "Alergia anestesia": {"checked": False, "detail": ""},
            "Hemorragias": {"checked": True, "detail": ""},
            "Diabetes": {"checked": True, "detail": ""},
            "Enf. cardíaca": {"checked": True, "detail": ""},
        })
        a = alertas_de_antecedentes(fondo(), f033)
        self.assertEqual(claves(a), {"alergia_antibiotico", "hemorragico", "embarazo",
                                     "diabetes", "cardiovascular"})
        fuentes = {x["clave"]: x["fuente"] for x in a}
        self.assertEqual(fuentes["cardiovascular"], "Formulario 033: «Enf. cardíaca»")
        self.assertEqual(fuentes["embarazo"], "Formulario 033: embarazada")

    def test_la_alergia_concreta_prevalece_sobre_la_casilla_generica(self):
        f033 = SimpleNamespace(embarazada=None, antecedentes_personales={
            "Alergia antibiótico": {"checked": True}})
        a = alertas_de_antecedentes(fondo(alergias="penicilina"), f033)
        self.assertEqual(claves(a), {"alergia_penicilina"})


class ReglasDeReceta(SimpleTestCase):
    def revisar(self, receta, **antecedentes):
        return revisar_receta(receta, alertas_de_antecedentes(fondo(**antecedentes)))

    def test_amoxicilina_a_alergico_a_penicilina(self):
        [c] = self.revisar("Amoxicilina 500 mg c/8h por 7 días", alergias="penicilina")
        self.assertEqual(c["nivel"], "alto")
        self.assertIn("amoxicilina", c["titulo"])
        self.assertIn("Alergias: «penicilina»", c["fuente"])

    def test_cefalosporina_es_reaccion_cruzada_de_nivel_medio(self):
        [c] = self.revisar("Cefalexina 500 mg", alergias="penicilina")
        self.assertEqual((c["clave"], c["nivel"]), ("alergia_penicilina", "medio"))

    def test_aine_a_anticoagulado(self):
        [c] = self.revisar("Ibuprofeno 400 mg cada 8 horas", medicacion="Warfarina")
        self.assertEqual((c["clave"], c["nivel"]), ("anticoagulado", "alto"))
        self.assertIn("ibuprofeno", c["titulo"])

    def test_doxiciclina_en_el_embarazo(self):
        choques = self.revisar("Doxiciclina 100 mg", embarazada=True)
        self.assertEqual([(c["clave"], c["nivel"]) for c in choques], [("embarazo", "alto")])

    def test_receta_compatible_no_avisa(self):
        self.assertEqual(self.revisar("Paracetamol 1 g c/8h. Clindamicina 300 mg",
                                      alergias="penicilina", medicacion="warfarina"), [])

    def test_varios_choques_a_la_vez(self):
        choques = self.revisar("Amoxicilina 500 mg\nKetorolaco 10 mg",
                               alergias="penicilina", medicacion="clopidogrel")
        self.assertEqual({c["clave"] for c in choques}, {"alergia_penicilina", "anticoagulado"})

    def test_sin_alertas_no_hay_choques(self):
        self.assertEqual(revisar_receta("Amoxicilina 500 mg", []), [])


class EndpointsDeAlertas(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica alertas")
        self.doctor = User.objects.create_user(email="doc@alertas.ec", password="superseguro123",
                                               role="doctor", tenant=self.tenant)
        self.recepcion = User.objects.create_user(email="rec@alertas.ec", password="superseguro123",
                                                  role="reception", tenant=self.tenant)
        self.paciente = Patient.objects.create(tenant=self.tenant, first_name="Ana",
                                               last_name="Pérez", national_id="0102030405")
        MedicalBackground.objects.create(patient=self.paciente, allergies="Penicilina",
                                         medications="Rivaroxabán 20 mg")
        self.url = f"/api/v1/patients/{self.paciente.id}/alertas/"

    def test_el_doctor_ve_las_alertas_y_queda_auditado(self):
        self.client.force_authenticate(self.doctor)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual({a["clave"] for a in r.data["alertas"]}, {"alergia_penicilina", "anticoagulado"})
        self.assertTrue(AuditLog.objects.filter(user=self.doctor, action="view_clinical_alerts",
                                                entity_id=str(self.paciente.id)).exists())

    def test_usa_el_ultimo_formulario_033(self):
        Form033Record.objects.create(tenant=self.tenant, patient=self.paciente, date=date(2025, 1, 1),
                                     antecedentes_personales={"Diabetes": {"checked": True}})
        Form033Record.objects.create(tenant=self.tenant, patient=self.paciente, date=date(2026, 1, 1),
                                     embarazada=True)
        self.client.force_authenticate(self.doctor)
        alertas = {a["clave"] for a in self.client.get(self.url).data["alertas"]}
        self.assertIn("embarazo", alertas)
        self.assertNotIn("diabetes", alertas)

    def test_recepcion_no_tiene_acceso(self):
        self.client.force_authenticate(self.recepcion)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url + "revisar/", {"texto": "Amoxicilina"}).status_code, 403)
        self.assertFalse(AuditLog.objects.filter(user=self.recepcion).exists())

    def test_paciente_de_otra_clinica(self):
        otra = Tenant.objects.create(name="Otra")
        ajeno = Patient.objects.create(tenant=otra, first_name="X", last_name="Y", national_id="1")
        self.client.force_authenticate(self.doctor)
        self.assertEqual(self.client.get(f"/api/v1/patients/{ajeno.id}/alertas/").status_code, 404)

    def test_revisar_receta(self):
        self.client.force_authenticate(self.doctor)
        r = self.client.post(self.url + "revisar/", {"texto": "Amoxicilina 500 mg\nIbuprofeno 400 mg"},
                             format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual({c["clave"] for c in r.data["choques"]}, {"alergia_penicilina", "anticoagulado"})
        self.assertTrue(AuditLog.objects.filter(action="check_prescription_alerts").exists())

    def test_revisar_sin_texto(self):
        self.client.force_authenticate(self.doctor)
        self.assertEqual(self.client.post(self.url + "revisar/", {"texto": "  "}, format="json").status_code, 400)
        self.assertEqual(self.client.post(self.url + "revisar/", {"texto": "x" * 5001},
                                          format="json").status_code, 400)


class DetalleDelFormulario033(SimpleTestCase):
    def test_el_detalle_de_la_casilla_concreta_la_alergia(self):
        f033 = SimpleNamespace(embarazada=None, antecedentes_personales={
            "Alergia antibiótico": {"checked": True, "detail": "Amoxicilina, urticaria"}})
        [a] = alertas_de_antecedentes(None, f033)
        self.assertEqual(a["clave"], "alergia_penicilina")
        self.assertEqual(a["fuente"], "Formulario 033 (Alergia antibiótico): «Amoxicilina»")
        [c] = revisar_receta("Amoxicilina 875 mg", [a])
        self.assertEqual(c["nivel"], "alto")

    def test_detalle_de_una_casilla_sin_marcar_no_cuenta(self):
        f033 = SimpleNamespace(embarazada=None, antecedentes_personales={
            "Alergia antibiótico": {"checked": False, "detail": "penicilina"}})
        self.assertEqual(alertas_de_antecedentes(None, f033), [])

    def test_otro_recoge_medicacion_y_condiciones(self):
        f033 = SimpleNamespace(embarazada=None, antecedentes_personales={
            "Otro": {"checked": True, "detail": "Toma Xarelto. Zoledronato por osteoporosis"}})
        self.assertEqual(claves(alertas_de_antecedentes(None, f033)), {"anticoagulado", "bifosfonatos"})

    def test_casilla_generica_con_detalle_no_reconocido(self):
        f033 = SimpleNamespace(embarazada=None, antecedentes_personales={
            "Alergia antibiótico": {"checked": True, "detail": "no recuerda cuál"}})
        [a] = alertas_de_antecedentes(None, f033)
        self.assertEqual(a["clave"], "alergia_antibiotico")
        self.assertIn("no recuerda cuál", a["detalle"])
