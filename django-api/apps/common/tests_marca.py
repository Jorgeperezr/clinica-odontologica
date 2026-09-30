"""
La plataforma se llama Clinube.

La marca de la plataforma y la de cada clínica son cosas distintas: la
primera sale en lo que ve el personal (correos del sistema, título de la
API, configuración de la plataforma); la segunda, en todo lo que recibe
el paciente. Aquí se fija la primera y que no se cuele en la segunda.
"""

from django.conf import settings
from django.test import TestCase

from apps.common.models import PlatformConfiguration, Tenant


class MarcaDeLaPlataforma(TestCase):
    def test_nombre_de_la_plataforma(self):
        self.assertEqual(settings.MARCA, "Clinube")
        self.assertEqual(PlatformConfiguration.get_solo().platform_name, "Clinube")

    def test_el_remitente_por_omision_lleva_la_marca(self):
        self.assertIn("Clinube", settings.DEFAULT_FROM_EMAIL)

    def test_la_clinica_conserva_su_propio_nombre(self):
        t = Tenant.objects.create(name="Sonrisa Feliz")
        self.assertEqual(str(t), "Sonrisa Feliz")
