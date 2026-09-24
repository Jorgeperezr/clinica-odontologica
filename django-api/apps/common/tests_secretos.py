"""
Que un token de un tercero no acabe en claro en la base.

Lo que se comprueba no es que `cryptography` cifre —eso es la
biblioteca— sino las tres decisiones de este proyecto: que lo guardado
no contenga el secreto, que un secreto ilegible no reviente el envío de
recordatorios, y que la pista que ve el panel no permita reconstruirlo.
"""

from django.test import SimpleTestCase, override_settings

from apps.common.secretos import cifrar, descifrar, pista

TOKEN = "EAAG1234muyLargoYSecreto567890abcdef"


class CifrarTests(SimpleTestCase):
    def test_ida_y_vuelta(self):
        self.assertEqual(descifrar(cifrar(TOKEN)), TOKEN)

    def test_lo_guardado_NO_contiene_el_secreto(self):
        guardado = cifrar(TOKEN)
        self.assertNotIn(TOKEN, guardado)
        self.assertNotIn(TOKEN[8:20], guardado)

    def test_dos_cifrados_del_mismo_token_son_distintos(self):
        # Fernet mete un vector aleatorio. Si salieran iguales, quien
        # mire la base sabría qué clínicas comparten credenciales.
        self.assertNotEqual(cifrar(TOKEN), cifrar(TOKEN))

    def test_vacio_se_queda_vacio(self):
        for nada in ("", "   ", None):
            self.assertEqual(cifrar(nada), "")

    def test_un_secreto_ilegible_no_lanza(self):
        # Pasa de verdad si se cambia DJANGO_SECRET_KEY. Tiene que
        # traducirse en «sin WhatsApp configurado», no en un 500 que
        # tumbe los recordatorios de todas las clínicas.
        for basura in ("v1:no-es-fernet", "texto suelto", "", None):
            self.assertEqual(descifrar(basura), "")

    @override_settings(SECRET_KEY="otra-clave-completamente-distinta-0123456789")
    def test_con_otra_clave_secreta_no_se_descifra(self):
        # Se cifra con la clave de las pruebas y se lee con otra: el
        # `override` aplica a la lectura, que es lo que se quiere probar.
        self.assertEqual(descifrar(CIFRADO_CON_LA_CLAVE_ORIGINAL), "")


class PistaTests(SimpleTestCase):
    def test_solo_los_ultimos_cuatro(self):
        self.assertEqual(pista(TOKEN), "…cdef")

    def test_no_permite_reconstruir_el_token(self):
        self.assertNotIn(TOKEN[:-4], pista(TOKEN))

    def test_algo_muy_corto_no_da_pista(self):
        # Con tres caracteres, la «pista» sería el secreto entero.
        self.assertEqual(pista("abc"), "")


CIFRADO_CON_LA_CLAVE_ORIGINAL = cifrar(TOKEN)
