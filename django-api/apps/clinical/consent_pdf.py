"""
Consentimiento informado en PDF profesional (Sprint 37).

Mismo patrón e infraestructura que la solicitud de examen: un builder que
recibe diccionarios ya resueltos por la vista y dibuja con reportlab.
Reutiliza los helpers de fecha/firma de exam_request_pdf.

Estructura del documento: encabezado con logo y datos de la clínica,
datos del paciente y del profesional, secciones del consentimiento
(procedimiento, beneficios, riesgos, alternativas, declaración,
observaciones), y bloque final de firmas (paciente y profesional) con
lugar/fecha y espacio para huella.
"""

import io

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from apps.clinical.exam_request_pdf import _decode_signature

# Sin colores ni tipografías propias: la apariencia la aporta
# `apps.common.document_style` (Sprint 63).


def _wrap(c, text, x, y, maxw, font="Helvetica", size=10, leading=5):
    """Dibuja texto con envoltura simple. Devuelve la nueva y."""
    c.setFont(font, size)
    for paragraph in str(text or "").split("\n"):
        words = paragraph.split()
        line = ""
        if not words:
            y -= leading * mm
            continue
        for w in words:
            test = f"{line} {w}".strip()
            if c.stringWidth(test, font, size) > maxw:
                c.drawString(x, y, line)
                y -= leading * mm
                line = w
            else:
                line = test
        c.drawString(x, y, line)
        y -= leading * mm
    return y


def build_consent_pdf(clinic, professional, patient, consent, style=None):
    """
    clinic:       {name, logo_reader|None, address, phone, email}
    professional: {full_name, specialty, license_number, signature_b64|None}
    patient:      {full_name, national_id, birth_date, age, sex, history_number}
    consent:      {title, procedure, benefits, risks, alternatives, body_text,
                   observations, patient_signature_b64|None, signed_place, signed_date}
    style:        DocumentStyle de `apps.common.document_style`. Si no se
                  pasa se usa el estilo por defecto, que reproduce el
                  aspecto anterior al motor de estilos.

    El encabezado, el pie y la marca de agua los dibuja el motor; aquí se
    compone solo el CONTENIDO del consentimiento.
    """
    from apps.common.document_style import get_document_style

    style = style or get_document_style(None)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=style.page_size)
    width, height = style.page_size
    ml, mr = style.content_left, style.content_right
    maxw = mr - ml

    def header():
        """Encabezado y marca de agua de la página actual."""
        style.draw_watermark(c)
        return style.draw_header(c, clinic=clinic, professional=professional)

    y = header()

    def ensure(space):
        """Salta de página conservando encabezado, pie y marca de agua."""
        nonlocal y
        if y - space < style.margin_bottom + 12 * mm:
            style.draw_footer(c, clinic=clinic)
            c.showPage()
            y = header()

    # ── Título ──
    c.setFillColor(style.title_color)
    c.setFont(style.font_bold, style.title_size - 3)
    c.drawCentredString(width / 2, y, "CONSENTIMIENTO INFORMADO")
    y -= 6 * mm
    c.setFont(style.font_bold, style.size + 1)
    c.setFillColor(style.primary)
    y = _wrap(c, consent.get("title"), ml, y, maxw,
              font=style.font_bold, size=style.size + 1, leading=5.5)
    y -= 3 * mm

    # ── Paciente y profesional (dos columnas) ──
    def kv(label, value, x, yy):
        c.setFillColor(style.secondary)
        c.setFont(style.font, style.size - 2)
        c.drawString(x, yy, label.upper())
        c.setFillColor(style.ink)
        c.setFont(style.font, style.size - 0.5)
        c.drawString(x, yy - 4 * mm, str(value) if value not in (None, "") else "—")

    col2 = ml + 92 * mm
    kv("Paciente", patient.get("full_name"), ml, y)
    kv("Profesional", professional.get("full_name"), col2, y)
    y -= 10 * mm
    kv("Identificación", patient.get("national_id"), ml, y)
    kv("Especialidad", professional.get("specialty") or "Odontología", col2, y)
    y -= 10 * mm
    kv("Nac. / Edad", f"{patient.get('birth_date') or '—'}  ·  {patient.get('age') or '—'}", ml, y)
    kv("Registro prof.", professional.get("license_number") or "—", col2, y)
    y -= 10 * mm
    kv("Sexo", patient.get("sex"), ml, y)
    kv("Historia clínica", patient.get("history_number"), col2, y)
    y -= 12 * mm

    c.setStrokeColor(style.separator)
    c.setLineWidth(0.5)
    c.line(ml, y, mr, y)
    y -= 8 * mm

    # ── Secciones del consentimiento ──
    def section(title, text):
        nonlocal y
        if not text:
            return
        ensure(24 * mm)
        c.setFillColor(style.primary)
        c.setFont(style.font_bold, style.size)
        c.drawString(ml, y, title.upper())
        y -= 6 * mm
        c.setFillColor(style.ink)
        y = _wrap(c, text, ml, y, maxw, font=style.font,
                  size=style.size - 0.5, leading=5)
        y -= 4 * mm

    section("Descripción del procedimiento", consent.get("procedure") or consent.get("body_text"))
    section("Beneficios", consent.get("benefits"))
    section("Riesgos y posibles complicaciones", consent.get("risks"))
    section("Alternativas terapéuticas", consent.get("alternatives"))
    # Declaración: si hay secciones estructuradas, body_text es la declaración
    if consent.get("procedure"):
        section("Declaración de aceptación", consent.get("body_text"))
    section("Observaciones", consent.get("observations"))

    # ── Firmas ──
    # Reserva: firmas (≈40 mm) + recuadro de huella (≈22 mm) + aire. Si no
    # cabe, se salta de página antes de empezar el bloque.
    ensure(70 * mm)
    y = style.draw_signature(c, y, [
        {
            "caption": "Firma del paciente",
            "full_name": patient.get("full_name") or "",
            "image": _decode_signature(consent.get("patient_signature_b64")),
        },
        {
            "caption": "Firma del profesional",
            "full_name": professional.get("full_name") or "",
            "specialty": professional.get("specialty"),
            "license_number": professional.get("license_number"),
            "image": _decode_signature(professional.get("signature_b64")),
        },
    ])

    # Huella + lugar y fecha
    y -= 4 * mm
    c.setStrokeColor(style.separator)
    c.setLineWidth(0.5)
    c.rect(ml, y - 18 * mm, 24 * mm, 22 * mm)
    c.setFillColor(style.secondary)
    c.setFont(style.font, style.size - 3)
    c.drawCentredString(ml + 12 * mm, y - 21 * mm, "Huella (opcional)")
    c.setFillColor(style.ink)
    c.setFont(style.font, style.size - 0.5)
    lugar_fecha = f"Lugar y fecha: {consent.get('signed_place') or '________________'}, {consent.get('signed_date') or '____ / ____ / ______'}"
    c.drawString(ml + 32 * mm, y - 4 * mm, lugar_fecha)

    # ── Pie institucional ──
    # El pie institucional lo dibuja el motor con la configuración de la
    # clínica, igual en todos los documentos.
    style.draw_footer(c, clinic=clinic)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()
