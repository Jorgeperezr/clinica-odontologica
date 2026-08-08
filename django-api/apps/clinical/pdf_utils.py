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


def generate_consent_pdf(consent, signature_path=None, style=None, clinic=None) -> bytes:
    """
    Genera el PDF de un consentimiento informado con la firma incrustada.
    Devuelve los bytes del PDF (para guardar en Cloud Storage / FileField).

    `style` es el DocumentStyle de la clínica (Sprint 60).
    """
    from apps.common.document_style import get_document_style

    style = style or get_document_style(None)

    buffer = io.BytesIO()
    doc = style.platypus_doc(buffer, title=consent.title or "Consentimiento")
    styles = _base_styles(style)
    story = list(style.header_flowables(clinic=clinic))

    story.append(Paragraph(consent.title, styles["ClinicTitle"]))
    story.append(Spacer(1, 6))

    patient = consent.patient
    story.append(Paragraph(
        f"<b>Paciente:</b> {patient.full_name} &nbsp;&nbsp; "
        f"<b>Identificación:</b> {patient.national_id}",
        styles["Normal"],
    ))
    story.append(Spacer(1, 12))

    # Cuerpo del consentimiento (respeta saltos de línea básicos)
    for para in consent.body_text.split("\n"):
        if para.strip():
            story.append(Paragraph(para, styles["Normal"]))
            story.append(Spacer(1, 6))

    story.append(Spacer(1, 24))

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

    story.append(Paragraph("<b>Firma del paciente:</b>", styles["Normal"]))
    story.append(Spacer(1, 6))
    if signature_ok:
        story.append(Image(signature_path, width=6 * cm, height=3 * cm))
    else:
        story.append(Paragraph("[Firma registrada digitalmente]", styles["Normal"]))

    story.append(Spacer(1, 12))

    # Evidencia de registro interno (fecha/hora/IP)
    signed = consent.signed_at or datetime.now()
    evidence = [
        ["Fecha y hora de firma:", signed.strftime("%Y-%m-%d %H:%M:%S")],
        ["Registro (IP):", consent.ip_address or "—"],
    ]
    table = Table(evidence, colWidths=[5 * cm, 10 * cm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), style.font),
        ("FONTSIZE", (0, 0), (-1, -1), max(6, style.size - 2)),
        ("TEXTCOLOR", (0, 0), (-1, -1), style.secondary),
    ]))
    story.append(table)
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Este documento constituye un registro interno de la clínica.",
        styles["Small"],
    ))

    furniture = style.page_furniture(clinic=clinic)
    doc.build(story, onFirstPage=furniture, onLaterPages=furniture)
    return buffer.getvalue()


def generate_clinical_history_pdf(patient, evolutions, diagnoses, plans,
                                  style=None, clinic=None) -> bytes:
    """
    Exporta la historia clínica completa de un paciente a PDF (RF-HCL-08).

    `style` es el DocumentStyle de la clínica (Sprint 60). Sin él se usa
    el estilo por defecto, que reproduce el aspecto anterior.
    """
    from apps.common.document_style import get_document_style

    style = style or get_document_style(None)

    buffer = io.BytesIO()
    doc = style.platypus_doc(buffer, title="Historia clínica")
    styles = _base_styles(style)
    story = list(style.header_flowables(clinic=clinic))

    story.append(Paragraph("Historia Clínica", styles["ClinicTitle"]))
    story.append(Paragraph(
        f"<b>Paciente:</b> {patient.full_name} &nbsp;&nbsp; "
        f"<b>Identificación:</b> {patient.national_id}",
        styles["Normal"],
    ))
    story.append(Paragraph(
        f"<b>Fecha de emisión:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        styles["Small"],
    ))
    story.append(Spacer(1, 16))

    # Diagnósticos
    story.append(Paragraph("Diagnósticos", styles["Heading2"]))
    if diagnoses:
        for d in diagnoses:
            pieza = f"Pieza {d.tooth_fdi_code}: " if d.tooth_fdi_code else ""
            story.append(Paragraph(f"{d.date} — {pieza}{d.description}", styles["Normal"]))
    else:
        story.append(Paragraph("Sin diagnósticos registrados.", styles["Normal"]))
    story.append(Spacer(1, 12))

    # Evoluciones
    story.append(Paragraph("Evoluciones", styles["Heading2"]))
    if evolutions:
        for e in evolutions:
            story.append(Paragraph(
                f"<b>{e.date} — {e.get_type_display()}:</b> {e.notes}", styles["Normal"]
            ))
            story.append(Spacer(1, 4))
    else:
        story.append(Paragraph("Sin evoluciones registradas.", styles["Normal"]))
    story.append(Spacer(1, 12))

    # Planes de tratamiento
    story.append(Paragraph("Planes de tratamiento", styles["Heading2"]))
    if plans:
        for plan in plans:
            story.append(Paragraph(
                f"<b>Plan ({plan.get_status_display()})</b> — {plan.created_at.strftime('%Y-%m-%d')}",
                styles["Normal"],
            ))
            for item in plan.items.all():
                pieza = f" (pieza {item.tooth_fdi_code})" if item.tooth_fdi_code else ""
                story.append(Paragraph(
                    f"&nbsp;&nbsp;• {item.treatment.name}{pieza} — {item.get_status_display()}",
                    styles["Normal"],
                ))
            story.append(Spacer(1, 6))
    else:
        story.append(Paragraph("Sin planes de tratamiento.", styles["Normal"]))

    furniture = style.page_furniture(clinic=clinic)
    doc.build(story, onFirstPage=furniture, onLaterPages=furniture)
    return buffer.getvalue()
