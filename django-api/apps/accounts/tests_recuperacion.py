"""
Recuperación de contraseña del personal por correo.

No tenía pruebas y el envío era silencioso: sin SMTP configurado el
correo no salía y nadie se enteraba. Aquí se fija que salga, que la
respuesta no revele si el correo existe y que un fallo quede registrado.
"""

from unittest import mock

from django.core import mail
from rest_framework.test import APITestCase

from apps.accounts.models import PasswordResetToken, User
from apps.common.models import Tenant

URL = "/api/v1/auth/recovery/request/"
GENERICA = "Si el correo existe, recibirás instrucciones."


class RecuperacionPorCorreo(APITestCase):
    def setUp(self):
        t = Tenant.objects.create(name="Clínica correo")
        self.doc = User.objects.create_user(email="doc@correo.ec", password="superseguro123",
                                            role="doctor", tenant=t)

    def test_el_personal_recibe_el_codigo(self):
        r = self.client.post(URL, {"email": "doc@correo.ec"})
        self.assertEqual(r.data["detail"], GENERICA)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["doc@correo.ec"])
        self.assertTrue(PasswordResetToken.objects.filter(user=self.doc).exists())

    def test_un_correo_desconocido_recibe_la_misma_respuesta_y_nada_sale(self):
        r = self.client.post(URL, {"email": "nadie@correo.ec"})
        self.assertEqual(r.data["detail"], GENERICA)
        self.assertEqual(mail.outbox, [])

    def test_si_el_smtp_falla_se_registra_y_la_respuesta_no_cambia(self):
        with mock.patch("apps.accounts.views.send_mail", side_effect=OSError("smtp caído")), \
                self.assertLogs("apps.accounts.views", level="ERROR") as registro:
            r = self.client.post(URL, {"email": "doc@correo.ec"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["detail"], GENERICA)
        self.assertIn("EMAIL_HOST", registro.output[0])
