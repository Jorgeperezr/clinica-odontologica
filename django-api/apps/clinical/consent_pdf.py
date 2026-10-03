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


def build_consent_pdf(clinic, professional, patient, consent, style=None):
    """
    clinic:       {name, logo_reader|None, address, phone, email}
    professional: {full_name, specialty, license_number, signature_b64|None}
    patient:      {full_name, national_id, birth_date, age, sex, history_number}
    consent:      {title, procedure, benefits, risks, alternatives, body_text,
                   observations, patient_signature_b64|None, signed_place, signed_date,
                   reference?, issued?}
    style:        DocumentStyle de `apps.common.document_style`. Si no se
                  pasa se usa el estilo por defecto.

    El encabezado, el pie y la marca de agua los dibuja el motor; aquí se
    compone solo el CONTENIDO del consentimiento. Dos pasadas para poder
    numerar «Página 1 de N»: un consentimiento de dos hojas se firma en
    la última, y quien lo archive tiene que saber que hay otra.
    """
    from apps.common.document_style import get_document_style

    style = style or get_document_style(None)
    _, paginas = _dibujar(clinic, professional, patient, consent, style)
    pdf, _ = _dibujar(clinic, professional, patient, consent, style, total_paginas=paginas)
    return pdf


def _dibujar(clinic, professional, patient, consent, style, total_paginas=None):
    from apps.common.document_style import fecha_documento

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=style.page_size)
    ml, mr = style.content_left, style.content_right
    maxw = mr - ml

    def header():
        """Encabezado y marca de agua de la página actual."""
        style.draw_watermark(c)
        return style.draw_header(c, clinic=clinic, professional=professional)

    def pie():
        style.draw_footer(c, clinic=clinic, page_number=c.getPageNumber(),
                          total_pages=total_paginas)

    y = header()

    def ensure(space):
        """Salta de página conservando encabezado, pie y marca de agua."""
        nonlocal y
        if y - space < style.margin_bottom + 12 * mm:
            pie()
            c.showPage()
            y = header()

    # ── Título y datos de control ──
    y = style.draw_title_block(
        c, y, "Consentimiento informado", subtitle=consent.get("title"),
        meta=[("N.º", str(consent.get("reference") or "")[:8].upper()),
              ("Emitido", fecha_documento(consent.get("issued")) if consent.get("issued") else None)],
    )

    # ── Paciente y profesional ──
    numero = 0

    def seccion(titulo):
        nonlocal y, numero
        numero += 1
        ensure(22 * mm)
        y = style.draw_section(c, y, titulo, numero)

    seccion("Datos del paciente y del profesional")
    nac = fecha_documento(patient.get("birth_date")) if patient.get("birth_date") else "—"
    edad = patient.get("age") if patient.get("age") not in (None, "", "—") else ""
    y = style.draw_fields(c, y, [
        [("Paciente", patient.get("full_name"), 2), ("Identificación", patient.get("national_id"))],
        [("Nacimiento / edad", f"{nac}  ·  {edad}" if edad else nac),
         ("Sexo", patient.get("sex")), ("Historia clínica", patient.get("history_number"))],
        [("Profesional", professional.get("full_name"), 2),
         ("Registro profesional", professional.get("license_number"))],
        [("Especialidad", professional.get("specialty") or "Odontología", 3)],
    ], columnas=3)

    # ── Secciones del consentimiento ──
    def section(title, text):
        nonlocal y
        if not text:
            return
        seccion(title)
        # La línea base del primer renglón, un cuerpo por debajo de la
        # banda: si no, las mayúsculas tocan el fondo de la sección.
        y -= style.size * 0.9
        c.setFillColor(style.ink)
        for parrafo in str(text).split("\n"):
            if not parrafo.strip():
                y -= 2 * mm
                continue
            for linea in ajustar_parrafo(c, parrafo, style.font, style.size - 0.5, maxw):
                ensure(style.leading + 2)
                c.setFillColor(style.ink)
                c.setFont(style.font, style.size - 0.5)
                c.drawString(ml, y, linea)
                y -= style.leading
        y -= 3 * mm

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
    ensure(72 * mm)
    y -= 4 * mm
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

    # Huella + lugar y fecha, en una misma franja
    y -= 3 * mm
    c.setStrokeColor(style.separator)
    c.setLineWidth(0.6)
    c.rect(ml, y - 22 * mm, 24 * mm, 22 * mm)
    c.setFillColor(style.secondary)
    c.setFont(style.font, style.size - 3)
    c.drawCentredString(ml + 12 * mm, y - 25.5 * mm, "Huella digital (opcional)")
    lugar = consent.get("signed_place") or "____________________"
    fecha = fecha_documento(consent.get("signed_date")) if consent.get("signed_date") \
        else "____ / ____ / ________"
    c.setFillColor(style.ink)
    c.setFont(style.font, style.size - 0.5)
    c.drawString(ml + 32 * mm, y - 8 * mm, f"Lugar: {lugar}")
    c.drawString(ml + 32 * mm, y - 15 * mm, f"Fecha: {fecha}")

    pie()
    paginas = c.getPageNumber()
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue(), paginas


def ajustar_parrafo(c, texto, fuente, cuerpo, ancho):
    from apps.common.document_style import ajustar

    return ajustar(c, texto, fuente, cuerpo, ancho)
