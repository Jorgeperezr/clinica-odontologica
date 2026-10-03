"""
Una receta no puede cortarse en silencio (Sprint 90).

Encontrado instrumentando el lienzo de dibujo y contando qué llegaba al
papel: una receta de **seis fármacos con su posología imprimía dos**. Las
otras cuatro no aparecían por ninguna parte, y la hoja salía con su
firma, su pie y su código de verificación — con todo el aspecto de estar
completa.

Ese es el daño real: no es que falte información, es que **no se nota
que falta**. El odontólogo entrega el papel, el paciente compra dos
medicamentos de seis y nadie se entera hasta que el tratamiento no
funciona.

El cuerpo hacía `break` al llegar al pie. El PDF de consentimiento ya
resolvía lo mismo saltando de página; la receta ahora hace igual.
"""

from django.test import SimpleTestCase
from reportlab.pdfgen import canvas as rl_canvas

import apps.clinical.prescription_pdf as receta_pdf

CLINICA = {"name": "Clínica Prueba", "address": "Av. Central 123",
           "phone": "+59399", "email": "a@b.ec"}
PROFESIONAL = {"full_name": "Dra. Elena Ruiz", "specialty": "Odontología",
               "license_number": "MSP-123"}
PACIENTE = {"full_name": "Ana Pérez Vela", "national_id": "0102030405"}


class _Espia(rl_canvas.Canvas):
    """Graba cada cadena que se dibuja, que es la única forma de saber
    qué acabó en el papel sin depender de un lector de PDF."""

    trazos = []

    def drawString(self, x, y, text, *a, **k):
        _Espia.trazos.append(text)
        return super().drawString(x, y, text, *a, **k)

    def drawRightString(self, x, y, text, *a, **k):
        _Espia.trazos.append(text)
        return super().drawRightString(x, y, text, *a, **k)

    def drawCentredString(self, x, y, text, *a, **k):
        _Espia.trazos.append(text)
        return super().drawCentredString(x, y, text, *a, **k)


def _generar(texto):
    """Devuelve (pdf, todo lo dibujado) para una receta con ese cuerpo."""
    original = receta_pdf.canvas.Canvas
    receta_pdf.canvas.Canvas = _Espia
    _Espia.trazos = []
    try:
        pdf = receta_pdf.build_prescription_pdf(
            clinic=CLINICA, professional=PROFESIONAL, patient=PACIENTE,
            prescription={"date": "2026-09-17", "notes": texto, "reference": "RX-1"},
        )
    finally:
        receta_pdf.canvas.Canvas = original
    return pdf, " ".join(_Espia.trazos)


def _receta_de(n_farmacos):
    farmacos = ["Amoxicilina 875/125 mg", "Ibuprofeno 600 mg", "Clorhexidina 0.12%",
                "Paracetamol 1 g", "Metronidazol 500 mg", "Omeprazol 20 mg",
                "Nistatina suspensión", "Ketorolaco 10 mg"]
    lineas = []
    for i, f in enumerate(farmacos[:n_farmacos], 1):
        lineas += [f"{i}. {f}",
                   "   Tomar 1 comprimido cada 8 horas durante 7 días.",
                   ""]
    return "\n".join(lineas), [x.strip() for x in lineas if x.strip()]


class NingunFarmacoSeQuedaFueraTests(SimpleTestCase):
    def test_una_receta_larga_imprime_todos_sus_farmacos(self):
        """
        El caso que fallaba: seis fármacos, de los que se imprimían dos.
        """
        texto, utiles = _receta_de(6)
        _, dibujado = _generar(texto)
        perdidas = [ln for ln in utiles if ln[:30] not in dibujado]
        self.assertEqual(
            perdidas, [],
            "la receta se cortó y estas líneas no llegaron al papel:\n  "
            + "\n  ".join(perdidas),
        )

    def test_ni_siquiera_una_receta_desmesurada(self):
        """Ocho fármacos: sigue sin perderse nada, en las hojas que hagan falta."""
        texto, utiles = _receta_de(8)
        _, dibujado = _generar(texto)
        self.assertEqual([ln for ln in utiles if ln[:30] not in dibujado], [])

    def test_la_receta_corriente_sigue_cabiendo_en_una_hoja(self):
        """
        No pasarse: lo normal son uno o dos fármacos y eso debe seguir
        siendo UNA hoja de talonario, no dos.
        """
        texto, _ = _receta_de(2)
        pdf, _ = _generar(texto)
        paginas = pdf.count(b"/Type /Page") - pdf.count(b"/Type /Pages")
        self.assertEqual(paginas, 1, "una receta corriente ocupa más de una hoja")

    def test_las_hojas_van_numeradas_con_su_total(self):
        """
        Si una receta ocupa dos hojas, cada una tiene que decirlo: entregar
        la primera y quedarse la segunda es el mismo daño que el corte.
        """
        texto, _ = _receta_de(6)
        _, dibujado = _generar(texto)
        self.assertIn("Página 1 de 2", dibujado)
        self.assertIn("Página 2 de 2", dibujado)

    def test_la_firma_y_el_codigo_van_en_la_ultima_hoja(self):
        texto, _ = _receta_de(6)
        _, dibujado = _generar(texto)
        self.assertIn("MSP-123", dibujado)
        self.assertIn("RX-1", dibujado)

    def test_la_continuacion_se_anuncia(self):
        """Quien recibe la segunda hoja debe saber de qué es."""
        texto, _ = _receta_de(6)
        _, dibujado = _generar(texto)
        self.assertIn("continuación", dibujado)


class LaOrdenDeExamenesTampocoSeCortaTests(SimpleTestCase):
    """
    El mismo fallo con otra forma. `paragraph` no comprobaba ningún suelo:
    seguía bajando la coordenada y con un texto largo escribía POR DEBAJO
    del papel. Medido antes de corregirlo: con 3808 caracteres de
    justificación se perdían 7 líneas, y con 7616 se perdían 42. El PDF
    salía sin una queja y con la firma en su sitio.

    Una justificación truncada invalida la orden para lo único que sirve:
    explicarle al radiólogo qué se busca.
    """

    def _generar(self, justificacion):
        import apps.clinical.exam_request_pdf as orden_pdf

        class Medidor(rl_canvas.Canvas):
            alturas = []

            def drawString(self, x, y, text, *a, **k):
                Medidor.alturas.append(y)
                return super().drawString(x, y, text, *a, **k)

        original = orden_pdf.canvas.Canvas
        orden_pdf.canvas.Canvas = Medidor
        Medidor.alturas = []
        try:
            orden_pdf.build_exam_request_pdf(
                clinic=CLINICA, professional=PROFESIONAL,
                patient={**PACIENTE, "birth_date": None},
                exam={"date": "2026-09-17", "exam_type": "Radiografía periapical",
                      "justification": justificacion, "observations": "",
                      "reference": "EX-1"},
            )
        finally:
            orden_pdf.canvas.Canvas = original
        return Medidor.alturas

    def test_una_justificacion_larga_no_se_sale_del_papel(self):
        texto = ("Paciente refiere dolor intenso en región posterior derecha con "
                 "sensibilidad al frío y a la percusión vertical; se observa lesión "
                 "cariosa profunda con posible compromiso pulpar. ") * 16
        alturas = self._generar(texto)
        fuera = [y for y in alturas if y < 0]
        self.assertEqual(
            fuera, [],
            f"{len(fuera)} líneas se dibujaron por debajo del borde del papel",
        )

    def test_una_orden_corriente_sigue_en_una_hoja(self):
        alturas = self._generar("Dolor en pieza 46, se solicita periapical.")
        self.assertTrue(all(y > 0 for y in alturas))
