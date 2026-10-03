"""
Documentos con formato formal: fechas en la hora de la clínica, receta
con quien la emite y páginas numeradas con su total.

Las fechas son lo delicado. El servidor corre en UTC y la clínica en
Ecuador (UTC−5): a partir de las 19:00, un documento que escribiera la
fecha UTC ponía la de mañana. Pasaba en el pie de todos los documentos y
en la hora del pedido de examen.
"""

from datetime import UTC, date, datetime
from unittest import mock

from django.test import SimpleTestCase, override_settings
from reportlab.pdfgen import canvas as rl_canvas

from apps.common.document_style import fecha_documento, get_document_style

TARDE_UTC = datetime(2026, 9, 30, 1, 22, tzinfo=UTC)   # 29/09 20:22 en Ecuador


class _Espia(rl_canvas.Canvas):
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


def dibujado(modulo, funcion, **kwargs):
    original = modulo.canvas.Canvas
    modulo.canvas.Canvas = _Espia
    _Espia.trazos = []
    try:
        funcion(**kwargs)
    finally:
        modulo.canvas.Canvas = original
    return " | ".join(_Espia.trazos)


@override_settings(TIME_ZONE="America/Guayaquil", USE_TZ=True)
class FechasDeDocumento(SimpleTestCase):
    def test_una_hora_utc_se_escribe_en_la_hora_de_la_clinica(self):
        self.assertEqual(fecha_documento(TARDE_UTC, con_hora=True), "29/09/2026 20:22")
        self.assertEqual(fecha_documento(TARDE_UTC), "29/09/2026")

    def test_fechas_sueltas_y_texto(self):
        self.assertEqual(fecha_documento(date(2026, 1, 5)), "05/01/2026")
        self.assertEqual(fecha_documento("2026-01-05"), "05/01/2026")
        self.assertEqual(fecha_documento(None), "—")
        self.assertEqual(fecha_documento("pendiente"), "pendiente")

    def test_el_pie_lleva_la_fecha_de_la_clinica(self):
        import apps.clinical.exam_request_pdf as examen

        with mock.patch("django.utils.timezone.now", return_value=TARDE_UTC):
            texto = dibujado(examen, examen.build_exam_request_pdf, **_EXAMEN)
        self.assertIn("29/09/2026", texto)
        self.assertNotIn("30/09/2026", texto)

    def test_el_pedido_de_examen_dice_la_hora_local(self):
        import apps.clinical.exam_request_pdf as examen

        texto = dibujado(examen, examen.build_exam_request_pdf, **_EXAMEN)
        self.assertIn("29/09/2026 20:22", texto)
        self.assertNotIn("01:22", texto)


_EXAMEN = dict(
    clinic={"name": "Clínica Prueba"},
    professional={"full_name": "Dra. Elena Ruiz", "license_number": "MSP-9"},
    patient={"full_name": "Ana Pérez", "national_id": "0102030405", "age": "30 años",
             "sex": "Femenino", "history_number": "0102030405"},
    exam={"datetime": TARDE_UTC, "category": "Rayos X", "detail": "Panorámica",
          "justification": "Control", "observations": "", "priority": "Normal",
          "urgent": True, "reference": "dc3b97e6-cf16"},
    style=None,
)


class DocumentosFormales(SimpleTestCase):
    def test_titulo_numero_y_paginas_con_total(self):
        import apps.clinical.exam_request_pdf as examen

        texto = dibujado(examen, examen.build_exam_request_pdf, **_EXAMEN)
        for esperado in ("SOLICITUD DE EXAMEN COMPLEMENTARIO", "DC3B97E6", "PRIORIDAD URGENTE",
                         "1. DATOS DEL PACIENTE", "Página 1 de 1"):
            self.assertIn(esperado, texto)

    def test_el_consentimiento_numera_sus_hojas(self):
        import apps.clinical.consent_pdf as consentimiento

        largo = "\n".join(["Riesgo descrito con detalle suficiente para ocupar una línea."] * 90)
        texto = dibujado(consentimiento, consentimiento.build_consent_pdf,
                         clinic={"name": "C"}, professional={"full_name": "Dra. R"},
                         patient={"full_name": "Ana"},
                         consent={"title": "Extracción", "risks": largo, "body_text": "Acepto",
                                  "procedure": "Extracción simple"},
                         style=get_document_style(None))
        import re

        # La segunda pasada (la que se entrega) numera con el total; todas
        # sus hojas dicen el mismo total y la última es la N de N.
        numeradas = [(int(a), int(b)) for a, b in re.findall(r"Página (\d+) de (\d+)", texto)]
        total = numeradas[-1][1]
        self.assertGreaterEqual(total, 2)
        self.assertEqual(numeradas, [(n, total) for n in range(1, total + 1)])
        self.assertIn("CONSENTIMIENTO INFORMADO", texto)

    def test_un_valor_largo_no_se_sale_de_su_casilla(self):
        from reportlab.lib.pagesizes import A4

        from apps.common.document_style import recortar

        c = rl_canvas.Canvas("/dev/null", pagesize=A4)
        texto = recortar(c, "Nombre extraordinariamente largo " * 10, "Helvetica", 10, 100)
        self.assertTrue(texto.endswith("…"))
        self.assertLessEqual(c.stringWidth(texto, "Helvetica", 10), 100)


class RecetaConQuienLaEmite(SimpleTestCase):
    """
    Una evolución registrada por alguien sin ficha de doctor asignada
    (un administrador que también atiende) daba una receta sin nombre ni
    registro. Ahora se toma de quien la escribió.
    """

    def test_sin_doctor_en_la_evolucion_usa_a_quien_la_escribio(self):
        from rest_framework.test import APIRequestFactory

        from apps.clinical import sprint22_views

        usuario = mock.Mock(full_name="Dra. Admin Demo", role="admin", is_authenticated=True)
        evolucion = mock.Mock(doctor=None, created_by_id=7, created_by=usuario, notes="Rp",
                              date=date(2026, 9, 29), id="e1")
        evolucion.patient.full_name = "Ana"
        evolucion.patient.national_id = "1"
        evolucion.patient.birth_date = None
        vista = sprint22_views.PrescriptionPDFView()
        request = APIRequestFactory().get("/")
        request.tenant = mock.Mock()
        request.user = usuario
        with mock.patch.object(sprint22_views.Evolution.objects, "select_related") as sel, \
                mock.patch("apps.agenda.models.Doctor.objects.filter") as doctores, \
                mock.patch("apps.clinical.prescription_pdf.build_prescription_pdf",
                           return_value=b"%PDF") as construir, \
                mock.patch("apps.common.document_style.clinic_snapshot", return_value={}), \
                mock.patch("apps.common.document_style.get_document_style"), \
                mock.patch.object(sprint22_views.AuditLog.objects, "create"):
            sel.return_value.get.return_value = evolucion
            doctores.return_value.first.return_value = None
            vista.get(request, pk="e1")
        profesional = construir.call_args.kwargs["professional"]
        self.assertEqual(profesional["full_name"], "Dra. Admin Demo")
