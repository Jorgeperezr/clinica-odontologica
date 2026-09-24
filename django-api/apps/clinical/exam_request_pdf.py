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
from datetime import date

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

# Este documento ya no define colores ni tipografías propias: todo sale
# de `apps.common.document_style`, que es el único punto donde se
# configura el aspecto de los documentos (Sprint 63).


def _age_from_birth(birth):
    if not birth:
        return "—"
    today = date.today()
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
    exam:         {datetime, category, detail, justification, observations, priority, urgent}
    style:        DocumentStyle de `apps.common.document_style`. Si no se
                  pasa, se usa el estilo por defecto, que reproduce el
                  aspecto que este documento tenía antes del Sprint 60.

    El encabezado, el pie y la marca de agua los dibuja el motor de
    estilos; aquí solo se compone el CONTENIDO de la solicitud.
    """
    from apps.common.document_style import get_document_style

    style = style or get_document_style(None)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=style.page_size)
    width, height = style.page_size
    ml, mr = style.content_left, style.content_right

    def encabezado():
        style.draw_watermark(c)
        return style.draw_header(c, clinic=clinic, professional=professional)

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
        style.draw_footer(c, clinic=clinic)
        c.showPage()
        y = encabezado()

    # ── Título ──
    c.setFillColor(style.title_color)
    c.setFont(style.font_bold, style.title_size - 2)
    c.drawCentredString(width / 2, y, "SOLICITUD DE EXAMEN COMPLEMENTARIO")
    y -= 4 * mm
    if exam.get("urgent"):
        c.setFillColor(style.alert)
        c.setFont(style.font_bold, style.size)
        c.drawCentredString(width / 2, y - 3 * mm, "★ PRIORIDAD URGENTE")
        y -= 7 * mm
    y -= 6 * mm

    # ── Helper de secciones ──
    def section(title):
        nonlocal y
        c.setFillColor(style.primary)
        c.setFont(style.font_bold, style.size)
        c.drawString(ml, y, title.upper())
        c.setStrokeColor(style.separator)
        c.setLineWidth(0.5)
        c.line(ml, y - 2 * mm, mr, y - 2 * mm)
        y -= 8 * mm

    def field(label, value, x=None, inline=False):
        nonlocal y
        xx = x if x is not None else ml
        c.setFillColor(style.secondary)
        c.setFont(style.font, style.size - 1.5)
        c.drawString(xx, y, label.upper())
        c.setFillColor(style.ink)
        c.setFont(style.font, style.size + 0.5)
        c.drawString(xx, y - 5 * mm, str(value) if value not in (None, "") else "—")
        if not inline:
            y -= 11 * mm

    # ── Profesional ──
    section("Profesional solicitante")
    field("Nombre", professional.get("full_name"), x=ml, inline=True)
    field("Especialidad", professional.get("specialty") or "Odontología", x=ml + 85 * mm, inline=True)
    y -= 11 * mm
    field("Registro profesional", professional.get("license_number") or "—")

    # ── Paciente ──
    section("Datos del paciente")
    field("Nombre completo", patient.get("full_name"), x=ml, inline=True)
    field("Identificación", patient.get("national_id"), x=ml + 85 * mm, inline=True)
    y -= 11 * mm
    field("Edad", patient.get("age"), x=ml, inline=True)
    field("Sexo", patient.get("sex"), x=ml + 55 * mm, inline=True)
    field("Historia clínica", patient.get("history_number"), x=ml + 110 * mm, inline=True)
    y -= 11 * mm

    # ── Solicitud ──
    section("Detalle de la solicitud")
    field("Fecha y hora", exam.get("datetime"), x=ml, inline=True)
    field("Prioridad", exam.get("priority"), x=ml + 85 * mm, inline=True)
    y -= 11 * mm
    field("Tipo de examen", exam.get("category"), x=ml, inline=True)
    field("Examen solicitado", exam.get("detail"), x=ml + 85 * mm, inline=True)
    y -= 11 * mm

    def paragraph(label, text):
        nonlocal y
        c.setFillColor(style.secondary)
        c.setFont(style.font, style.size - 1.5)
        c.drawString(ml, y, label.upper())
        y -= 5 * mm
        c.setFillColor(style.ink)
        c.setFont(style.font, style.size)
        # Envoltura simple de texto
        words = str(text or "—").split()
        line, maxw = "", mr - ml
        # Suelo: por encima del bloque de firma, igual que en la receta.
        suelo = style.margin_bottom + 58 * mm

        def escribir(texto_linea):
            nonlocal y
            if y < suelo:
                sigue_en_otra_hoja()
            c.drawString(ml, y, texto_linea)
            y -= 5 * mm

        for w in words:
            test = f"{line} {w}".strip()
            if c.stringWidth(test, style.font, style.size) > maxw:
                escribir(line)
                line = w
            else:
                line = test
        escribir(line)
        y -= 4 * mm

    paragraph("Motivo / justificación clínica", exam.get("justification"))
    if exam.get("observations"):
        paragraph("Observaciones", exam.get("observations"))

    # ── Firma y sello ──
    # El bloque queda anclado abajo cuando el contenido es corto y baja
    # con el contenido cuando es largo, sin llegar a pisar el pie.
    sign_top = max(min(y - 4 * mm, style.margin_bottom + 52 * mm),
                   style.margin_bottom + 46 * mm)
    style.draw_signature(c, sign_top, [{
        "caption": "Firma y sello",
        "full_name": professional.get("full_name") or "",
        "specialty": professional.get("specialty"),
        "license_number": professional.get("license_number"),
        "image": _decode_signature(professional.get("signature_b64")),
    }])

    # ── Pie institucional ──
    # Lo dibuja el motor con la configuración de la clínica: mismo pie en
    # todos los documentos y desactivable desde Configuración.
    style.draw_footer(c, clinic=clinic)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()
