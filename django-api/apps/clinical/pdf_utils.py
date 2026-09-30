"""
Generación de PDFs para el módulo clínico (RF-HCL-07, RF-HCL-08).
Usa reportlab (Platypus) según la guía de la skill de PDF.
"""

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


def _base_styles(style=None):
    """
    Hoja de estilos del documento. Si se recibe un `DocumentStyle`
    (Sprint 60) los párrafos toman la tipografía y la paleta configuradas
    por la clínica; si no, se conservan los valores originales para no
    alterar los documentos ya emitidos.
    """
    styles = getSampleStyleSheet()
    if style is not None:
        base = style.paragraph_styles()
        # Se reexponen con los nombres que ya usaban estos generadores
        styles.add(ParagraphStyle(name="ClinicTitle", parent=base["DocTitle"]))
        styles.add(ParagraphStyle(name="Small", parent=base["DocSmall"]))
        styles["Normal"].fontName = style.font
        styles["Normal"].fontSize = style.size
        styles["Normal"].leading = style.leading
        styles["Normal"].textColor = style.ink
        styles["Heading2"].fontName = style.font_bold
        styles["Heading2"].fontSize = style.subtitle_size
        styles["Heading2"].textColor = style.subtitle_color
        return styles

    styles.add(ParagraphStyle(
        name="ClinicTitle", parent=styles["Title"], fontSize=16, spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        name="Small", parent=styles["Normal"], fontSize=8, textColor=colors.grey,
    ))
    return styles


def _construir(style, clinic, titulo, story, total=None):
    """
    Compone el documento y devuelve (pdf, páginas). Los generadores lo
    llaman dos veces —la segunda sabiendo el total— para escribir
    «Página x de N» en cada pie: una historia de tres hojas en la que
    falta una no se nota si el pie solo dice «Página 2». Cada pasada
    compone su propia historia, porque Platypus consume los flowables.
    """
    buffer = io.BytesIO()
    doc = style.platypus_doc(buffer, title=titulo)
    furniture = style.page_furniture(clinic=clinic, total_pages=total)
    doc.build(story, onFirstPage=furniture, onLaterPages=furniture)
    return buffer.getvalue(), doc.page


def _p(texto, estilo):
    """Paragraph con el texto escapado y los saltos de línea respetados."""
    from xml.sax.saxutils import escape

    return Paragraph(escape(str(texto or "—")).replace("\n", "<br/>"), estilo)


def generate_consent_pdf(consent, signature_path=None, style=None, clinic=None,
                         _total_paginas=None) -> bytes:
    """
    Genera el PDF de un consentimiento informado YA FIRMADO, con la firma
    incrustada y la evidencia del registro. Devuelve los bytes del PDF
    (para guardar en Cloud Storage / FileField).

    `style` es el DocumentStyle de la clínica (Sprint 60).
    """
    from apps.common.document_style import fecha_documento, get_document_style

    style = style or get_document_style(None)

    styles = _base_styles(style)
    story = list(style.header_flowables(clinic=clinic))
    story += style.title_flowables(
        "Consentimiento informado", subtitle=consent.title,
        meta=[("N.º", str(consent.id)[:8].upper()),
              ("Firmado", fecha_documento(consent.signed_at, con_hora=True) if consent.signed_at else None)],
    )

    patient = consent.patient
    story.append(style.section_flowable("Datos del paciente", 1))
    story.append(style.fields_table([
        [("Paciente", patient.full_name, 2), ("Identificación", patient.national_id)],
    ]))

    story.append(style.section_flowable("Contenido del consentimiento", 2))
    for para in (consent.body_text or "").split("\n"):
        if para.strip():
            story.append(_p(para, styles["Normal"]))
            story.append(Spacer(1, 4))

    # Firma. Validamos que la imagen sea legible antes de incrustarla,
    # porque reportlab la lee de forma perezosa al construir el documento
    # y una imagen corrupta rompería toda la generación del PDF.
    signature_ok = False
    if signature_path:
        try:
            from PIL import Image as PILImage

            with PILImage.open(signature_path) as im:
                im.verify()
            signature_ok = True
        except Exception:
            signature_ok = False

    story.append(style.section_flowable("Firma y registro", 3))
    firma = Image(signature_path, width=6 * cm, height=3 * cm) if signature_ok \
        else _p("[Firma registrada digitalmente]", styles["Normal"])
    signed = consent.signed_at or datetime.now()
    evidencia = Table([
        [firma, _p(
            f"Firma del paciente: {patient.full_name}\n"
            f"Fecha y hora de firma: {fecha_documento(signed, con_hora=True)}\n"
            f"Registro (IP): {consent.ip_address or '—'}", styles["Small"])],
    ], colWidths=[7 * cm, style.content_width - 7 * cm])
    evidencia.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("LINEBELOW", (0, 0), (0, 0), 0.6, style.ink),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(evidencia)
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Este documento constituye un registro interno de la clínica.",
        styles["Small"],
    ))

    pdf, paginas = _construir(style, clinic, consent.title or "Consentimiento", story, _total_paginas)
    if _total_paginas is None:
        return generate_consent_pdf(consent, signature_path, style, clinic, _total_paginas=paginas)
    return pdf


def generate_clinical_history_pdf(patient, evolutions, diagnoses, plans,
                                  style=None, clinic=None, background=None,
                                  _total_paginas=None) -> bytes:
    """
    Exporta la historia clínica completa de un paciente a PDF (RF-HCL-08).

    `style` es el DocumentStyle de la clínica (Sprint 60). Antes eran
    párrafos corridos («2026-09-30 — Receta: …»); ahora cada bloque es una
    tabla con sus columnas, que es como se lee y se archiva una historia.
    """
    from apps.common.document_style import ahora_local, fecha_documento, get_document_style

    style = style or get_document_style(None)

    styles = _base_styles(style)
    celda = ParagraphStyle("celda", parent=styles["Normal"], fontSize=style.size - 1,
                           leading=(style.size - 1) * 1.3)
    story = list(style.header_flowables(clinic=clinic))
    story += style.title_flowables(
        "Historia clínica", subtitle=patient.full_name,
        meta=[("Identificación", patient.national_id),
              ("Emitida", fecha_documento(ahora_local(), con_hora=True))],
    )

    def tabla(cabecera, filas, anchos):
        datos = [cabecera] + [[_p(v, celda) for v in fila] for fila in filas]
        t = Table(datos, colWidths=[style.content_width * a for a in anchos], repeatRows=1)
        t.setStyle(style.table_style())
        return t

    numero = 0

    def seccion(titulo):
        nonlocal numero
        numero += 1
        story.append(style.section_flowable(titulo, numero))

    # Datos del paciente
    seccion("Datos del paciente")
    sexo = {"H": "Masculino", "M": "Femenino"}.get(getattr(patient, "sex", ""), getattr(patient, "sex", "") or "—")
    story.append(style.fields_table([
        [("Nombre", patient.full_name, 2), ("Identificación", patient.national_id)],
        [("Fecha de nacimiento", fecha_documento(patient.birth_date) if patient.birth_date else "—"),
         ("Sexo", sexo), ("Teléfono", getattr(patient, "phone", "") or "—")],
    ]))

    if background is not None:
        seccion("Antecedentes médicos")
        embarazo = {True: "Sí", False: "No"}.get(background.is_pregnant, "Sin dato")
        story.append(style.fields_table([
            [("Alergias", background.allergies or "Sin registro", 3)],
            [("Medicación habitual", background.medications or "Sin registro", 3)],
            [("Enfermedades y condiciones", background.conditions or "Sin registro", 2),
             ("Embarazo", embarazo)],
        ]))

    # Diagnósticos
    seccion("Diagnósticos")
    if diagnoses:
        story.append(tabla(
            ["Fecha", "Pieza", "CIE-10", "Diagnóstico"],
            [[fecha_documento(d.date), d.tooth_fdi_code or "—", d.code or "—", d.description]
             for d in diagnoses],
            [0.14, 0.09, 0.12, 0.65]))
    else:
        story.append(Paragraph("Sin diagnósticos registrados.", styles["Normal"]))

    # Evoluciones
    seccion("Evoluciones, recetas e indicaciones")
    if evolutions:
        def autor(e):
            if e.doctor_id:
                return e.doctor.full_name
            return getattr(e.created_by, "full_name", "") or "—"
        story.append(tabla(
            ["Fecha", "Tipo", "Profesional", "Detalle"],
            [[fecha_documento(e.date), e.get_type_display(), autor(e), e.notes] for e in evolutions],
            [0.13, 0.14, 0.2, 0.53]))
    else:
        story.append(Paragraph("Sin evoluciones registradas.", styles["Normal"]))

    # Planes de tratamiento
    seccion("Planes de tratamiento")
    if plans:
        for plan in plans:
            story.append(Paragraph(
                f"<b>Plan {plan.get_status_display().lower()}</b> · creado el "
                f"{fecha_documento(plan.created_at)}"
                + (f" · {plan.description}" if getattr(plan, "description", "") else ""),
                styles["Normal"]))
            story.append(Spacer(1, 3))
            items = list(plan.items.all())
            if items:
                story.append(tabla(
                    ["Tratamiento", "Pieza", "Estado"],
                    [[i.treatment.name, i.tooth_fdi_code or "—", i.get_status_display()] for i in items],
                    [0.6, 0.12, 0.28]))
            story.append(Spacer(1, 8))
    else:
        story.append(Paragraph("Sin planes de tratamiento.", styles["Normal"]))

    pdf, paginas = _construir(style, clinic, "Historia clínica", story, _total_paginas)
    if _total_paginas is None:
        return generate_clinical_history_pdf(patient, evolutions, diagnoses, plans, style, clinic,
                                             background, _total_paginas=paginas)
    return pdf
