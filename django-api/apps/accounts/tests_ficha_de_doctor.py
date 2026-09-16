"""
La ficha de doctor y el rol del usuario (Sprint 85).

Encontrado intentando agendar una cita en el panel: el desplegable de
doctores estaba vacío. La causa resultó ser más general que la semilla de
desarrollo: la ficha `Doctor` se creaba al DAR DE ALTA un usuario con ese
rol, pero no al cambiarle el rol a uno que ya existía.

El efecto en una clínica: se asciende a alguien a doctor, aparece como
doctor en la lista de usuarios, y en la agenda no existe. No se le puede
citar y nada dice por qué.
"""

from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.agenda.models import Doctor
from apps.common.models import Tenant


class LaFichaDeDoctorSigueAlRolTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Clínica Fichas", ruc="1790000085001")
        self.admin = User.objects.create_user(
            email="admin@fichas.ec", password="superseguro123",
            role="admin", tenant=self.tenant,
        )
        self.client.force_authenticate(user=self.admin)

    def test_al_dar_de_alta_un_doctor_se_crea_su_ficha(self):
        resp = self.client.post("/api/v1/users/", {
            "email": "nueva@fichas.ec", "full_name": "Dra. Nueva",
            "role": "doctor", "password": "superseguro123",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(
            Doctor.objects.filter(tenant=self.tenant, user__email="nueva@fichas.ec").exists()
        )

    def test_ascender_a_doctor_tambien_le_crea_la_ficha(self):
        """
        El fallo: esto dejaba a la persona con rol de doctor y sin ficha,
        así que no salía en la agenda.
        """
        recepcion = User.objects.create_user(
            email="recepcion@fichas.ec", password="superseguro123",
            role="reception", tenant=self.tenant, full_name="Ana Recepción",
        )
        self.assertFalse(Doctor.objects.filter(user=recepcion).exists())

        resp = self.client.patch(
            f"/api/v1/users/{recepcion.id}/", {"role": "doctor"}, format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(
            Doctor.objects.filter(tenant=self.tenant, user=recepcion).exists(),
            "se le cambió el rol a doctor pero sigue sin existir para la agenda",
        )

    def test_el_doctor_asciende_y_ya_se_puede_citar(self):
        """
        Lo que de verdad importa: que aparezca donde hace falta. Se
        comprueba contra el listado que alimenta el desplegable de la
        agenda, no contra la tabla.
        """
        u = User.objects.create_user(
            email="sube@fichas.ec", password="superseguro123",
            role="auxiliary", tenant=self.tenant, full_name="Luis Auxiliar",
        )
        self.client.patch(f"/api/v1/users/{u.id}/", {"role": "doctor"}, format="json")

        resp = self.client.get("/api/v1/doctors/")
        self.assertEqual(resp.status_code, 200, resp.data)
        listados = resp.data.get("results", resp.data)
        self.assertIn(
            "sube@fichas.ec", [d.get("email") or d.get("user_email") or
                               (d.get("user") or {}).get("email") for d in listados],
        )

    def test_no_se_duplica_la_ficha_al_editar_otras_cosas(self):
        resp = self.client.post("/api/v1/users/", {
            "email": "doble@fichas.ec", "full_name": "Dr. Doble",
            "role": "doctor", "password": "superseguro123",
        }, format="json")
        uid = resp.data["id"]
        for nombre in ("Dr. Doble Uno", "Dr. Doble Dos"):
            self.client.patch(f"/api/v1/users/{uid}/", {"full_name": nombre}, format="json")
        self.assertEqual(Doctor.objects.filter(user_id=uid).count(), 1)

    def test_quitarle_el_rol_no_borra_la_ficha(self):
        """
        Deliberado: de la ficha cuelgan citas e historia clínica. Perderlas
        por un cambio de puesto sería peor que tener una ficha de más.
        """
        resp = self.client.post("/api/v1/users/", {
            "email": "baja@fichas.ec", "full_name": "Dr. Baja",
            "role": "doctor", "password": "superseguro123",
        }, format="json")
        uid = resp.data["id"]
        self.client.patch(f"/api/v1/users/{uid}/", {"role": "reception"}, format="json")
        self.assertTrue(Doctor.objects.filter(user_id=uid).exists())
