"""
Las plantillas de .env nombran las variables que el gateway lee de verdad.

`.env.production.example` decía META_WHATSAPP_TOKEN y el gateway lee
META_ACCESS_TOKEN: con la plantilla rellenada al pie de la letra, el
token no llegaba, los envíos quedaban en modo simulado y ningún paciente
recibía su código de ingreso a la app. Nada fallaba en voz alta.
"""

from pathlib import Path

import pytest

from app.config import Settings

RAIZ = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("plantilla", [".env.example", ".env.production.example"])
def test_cada_variable_meta_existe_en_el_gateway(plantilla):
    campos = {nombre.upper() for nombre in Settings.model_fields}
    claves = [linea.split("=", 1)[0].strip()
              for linea in (RAIZ / plantilla).read_text(encoding="utf-8").splitlines()
              if linea.startswith("META_")]
    assert claves, f"{plantilla} no tiene variables META_"
    desconocidas = [c for c in claves if c not in campos]
    assert desconocidas == [], f"{plantilla}: el gateway no lee {desconocidas}"
