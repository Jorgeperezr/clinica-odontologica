"""
Solicitud de examen complementario en PDF (Sprint 36).

Documento formal para entregar al paciente o al centro de diagnóstico.
Diseño profesional listo para impresión: encabezado con logotipo y datos
de la clínica, datos del profesional (desde la sesión), datos del
paciente, contenido de la solicitud, espacio para firma y sello, y pie
institucional.

Sigue el patrón de los otros generadores del sistema (reportlab, un solo
builder que recibe diccionarios ya resueltos por la vista). No accede a la
base de datos: la vista arma los datos y este módulo solo dibuja.
"""

import base64
import io

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

_BLANCO = colors.white

# Este documento ya no define colores ni tipografías propias: todo sale
# de `apps.common.document_style`, que es el único punto donde se
# configura el aspecto de los documentos (Sprint 63).


def _age_from_birth(birth):
    if not birth:
        return "—"
    today = timezone.localdate()
    years = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    return f"{years} años"


def _decode_signature(signature_b64):
    """Devuelve un ImageReader de la firma o None. Acepta data-URI o base64 puro."""
    if not signature_b64:
        return None
    try:
        from reportlab.lib.utils import ImageReader
        raw = signature_b64.split(",", 1)[1] if "," in signature_b64 else signature_b64
        return ImageReader(io.BytesIO(base64.b64decode(raw)))
    except Exception:
        return None


def build_exam_request_pdf(clinic, professional, patient, exam, style=None):
    """
    clinic:       {name, logo_reader|None, address, phone, email}
    professional: {full_name, specialty, license_number, signature_b64|None}
    patient:      {full_name, national_id, age, sex, history_number}
    exam:         {datetime, category, detail, justification, observations, priority,
                   urgent, reference?}
    style:        DocumentStyle de `apps.common.document_style`. Si no se
                  pasa, se usa el estilo por defecto.

    El encabezado, el pie y la marca de agua los dibuja el motor de
    estilos; aquí solo se compone el CONTENIDO de la solicitud. Se dibuja
    dos veces para poder numerar «Página 1 de N», igual que la receta.
    """
    from apps.common.document_style import get_document_style

    style = style or get_document_style(None)
    _, paginas = _dibujar(clinic, professional, patient, exam, style)
    pdf, _ = _dibujar(clinic, professional, patient, exam, style, total_paginas=paginas)
    return pdf


def _dibujar(clinic, professional, patient, exam, style, total_paginas=None):
    from apps.common.document_style import ajustar, fecha_documento

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=style.page_size)
    ml, mr = style.content_left, style.content_right

    def encabezado():
        style.draw_watermark(c)
        return style.draw_header(c, clinic=clinic, professional=professional)

    def pie():
        style.draw_footer(c, clinic=clinic, page_number=c.getPageNumber(),
                          total_pages=total_paginas)

    y = encabezado()

    def sigue_en_otra_hoja():
        """
        Salta de hoja conservando encabezado, pie y marca de agua.

        `paragraph` no comprobaba ningún suelo: seguía bajando la `y` y
        con un texto largo escribía POR DEBAJO del papel. Medido: con
        3808 caracteres de justificación se perdían 7 líneas con
        coordenada negativa, y con 7616 se perdían 42. El PDF salía sin
        una queja y con su firma en su sitio.

        Una justificación clínica truncada en silencio invalida la orden
        para lo único que sirve: explicarle al radiólogo qué se busca.
        """
        nonlocal y
        pie()
        c.showPage()
        y = encabezado()

    # ── Título y datos de control ──
    referencia = str(exam.get("reference") or "")[:8].upper()
    y = style.draw_title_block(
        c, y, "Solicitud de examen complementario",
        meta=[("N.º", referencia), ("Fecha", fecha_documento(exam.get("datetime"), con_hora=True))],
    )
    if exam.get("urgent"):
        c.setFillColor(style.alert)
        c.roundRect(ml, y - 6 * mm, 42 * mm, 6 * mm, 1.5 * mm, stroke=0, fill=1)
        c.setFillColor(_BLANCO)
        c.setFont(style.font_bold, style.size - 1)
        c.drawCentredString(ml + 21 * mm, y - 4.2 * mm, "PRIORIDAD URGENTE")
        y -= 10 * mm

    # ── Datos ──
    y = style.draw_section(c, y, "Datos del paciente", 1)
    y = style.draw_fields(c, y, [
        [("Nombre completo", patient.get("full_name"), 2), ("Identificación", patient.get("national_id"))],
        [("Edad", patient.get("age")), ("Sexo", patient.get("sex")),
         ("Historia clínica", patient.get("history_number"))],
    ], columnas=3)

    y = style.draw_section(c, y, "Profesional solicitante", 2)
    y = style.draw_fields(c, y, [
        [("Nombre", professional.get("full_name"), 2),
         ("Registro profesional", professional.get("license_number"))],
        [("Especialidad", professional.get("specialty") or "Odontología", 3)],
    ], columnas=3)

    y = style.draw_section(c, y, "Examen solicitado", 3)
    y = style.draw_fields(c, y, [
        [("Tipo de examen", exam.get("category")), ("Examen", exam.get("detail")),
         ("Prioridad", exam.get("priority"))],
    ], columnas=3)

    # Suelo: por encima del bloque de firma, igual que en la receta.
    suelo = style.margin_bottom + 58 * mm

    def parrafo(etiqueta, texto):
        nonlocal y
        c.setFillColor(style.secondary)
        c.setFont(style.font_bold, style.size - 2)
        c.drawString(ml, y, etiqueta.upper())
        y -= 5 * mm
        c.setFillColor(style.ink)
        c.setFont(style.font, style.size)
        for linea in ajustar(c, texto or "—", style.font, style.size, mr - ml):
            if y < suelo:
                sigue_en_otra_hoja()
                c.setFillColor(style.ink)
                c.setFont(style.font, style.size)
            c.drawString(ml, y, linea)
            y -= style.leading
        y -= 3 * mm

    parrafo("Motivo / justificación clínica", exam.get("justification"))
    if exam.get("observations"):
        parrafo("Observaciones", exam.get("observations"))

    # ── Firma y sello ──
    # El bloque queda anclado abajo cuando el contenido es corto y baja
    # con el contenido cuando es largo, sin llegar a pisar el pie.
    if y < style.margin_bottom + 46 * mm:
        sigue_en_otra_hoja()
    sign_top = max(min(y - 4 * mm, style.margin_bottom + 52 * mm),
                   style.margin_bottom + 46 * mm)
    style.draw_signature(c, sign_top, [{
        "caption": "Firma y sello del profesional",
        "full_name": professional.get("full_name") or "",
        "specialty": professional.get("specialty"),
        "license_number": professional.get("license_number"),
        "image": _decode_signature(professional.get("signature_b64")),
    }])

    pie()
    paginas = c.getPageNumber()
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue(), paginas
