"""
Receta médica en PDF (Sprint 22, extraída a su propio módulo en el 64).

Sigue el patrón del resto de generadores: recibe diccionarios ya
resueltos por la vista y solo dibuja; no consulta la base de datos.

Antes vivía dentro de la vista con el membrete, los colores y las
tipografías escritos a mano, de modo que era el único documento clínico
que no seguía la identidad de la clínica. Ahora encabezado, pie, marca
de agua y firma los pone `apps.common.document_style` y aquí queda solo
el cuerpo de la receta.

La hoja es la que indique `page.prescription_size` (A5 por defecto): una
receta se imprime en talonario, y ese formato es parte del documento, no
una decisión de estilo.

firmaEC (Fase 2): la firma electrónica legal requiere el certificado
.p12 del doctor emitido por una entidad acreditada. El PDF que sale de
aquí queda listo para ese proceso — ver DEPLOY.md.
"""

import io

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def build_prescription_pdf(clinic, professional, patient, prescription, style=None):
    """
    clinic:       {name, logo_reader|None, address, phone, email}
    professional: {full_name, specialty, license_number, signature_b64|None}
    patient:      {full_name, national_id}
    prescription: {date, notes, reference}
    style:        DocumentStyle de `apps.common.document_style`.
    """
    from apps.clinical.exam_request_pdf import _decode_signature
    from apps.common.document_style import get_document_style

    style = style or get_document_style(None)
    style = style.for_page(style.s["page"].get("prescription_size", "A5"))

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=style.page_size)
    width = style.width
    ml, mr = style.content_left, style.content_right

    style.draw_watermark(c)
    y = style.draw_header(c, clinic=clinic, professional=professional)

    # ── Título ──
    c.setFillColor(style.title_color)
    c.setFont(style.font_bold, style.subtitle_size + 1)
    c.drawRightString(mr, y, "RECETA")
    c.setFillColor(style.secondary)
    c.setFont(style.font, style.size - 1)
    c.drawString(ml, y, f"Fecha: {prescription.get('date') or '—'}")
    y -= 8 * mm

    # ── Paciente ──
    c.setFillColor(style.ink)
    c.setFont(style.font, style.size)
    c.drawString(ml, y, f"Paciente: {patient.get('full_name') or '—'}")
    y -= 5 * mm
    c.drawString(ml, y, f"CI: {patient.get('national_id') or '—'}")
    y -= 4 * mm
    c.setStrokeColor(style.separator)
    c.setLineWidth(0.5)
    c.line(ml, y, mr, y)

    # ── Rx ──
    y -= 10 * mm
    c.setFillColor(style.primary)
    c.setFont(style.font_bold, style.title_size)
    c.drawString(ml, y, "Rx.")
    y -= 8 * mm

    c.setFillColor(style.ink)
    c.setFont(style.font, style.size)
    indent = ml + 4 * mm
    # Suelo del cuerpo: por encima del bloque de firma, que va anclado a
    # `margin_bottom + 52 mm` como en el resto de documentos.
    floor = style.margin_bottom + 56 * mm
    maxw = mr - indent
    for raw_line in (prescription.get("notes") or "").splitlines() or [""]:
        # Envoltura por ancho real, no por número de caracteres: con otra
        # tipografía o cuerpo, cortar a 70 caracteres se salía del papel.
        words = raw_line.split()
        line = ""
        for w in words:
            test = f"{line} {w}".strip()
            if c.stringWidth(test, style.font, style.size) > maxw:
                c.drawString(indent, y, line)
                y -= style.leading
                line = w
                if y < floor:
                    break
            else:
                line = test
        if y < floor:
            break
        c.drawString(indent, y, line)
        y -= style.leading

    # ── Firma ──
    style.draw_signature(c, style.margin_bottom + 52 * mm, [{
        "caption": "Firma y sello",
        "full_name": professional.get("full_name") or "",
        "specialty": professional.get("specialty"),
        "license_number": professional.get("license_number"),
        "image": _decode_signature(professional.get("signature_b64")),
    }])

    # ── Verificación ──
    # Identificador con el que cotejar la receta contra el sistema. Va en
    # la banda que queda entre la firma y la línea del pie.
    if prescription.get("reference"):
        c.setFillColor(style.secondary)
        c.setFont(style.font_italic, max(6, style.size - 3.5))
        c.drawCentredString(width / 2, style.margin_bottom + 10 * mm,
                            f"Verificación: {prescription['reference']}")

    style.draw_footer(c, clinic=clinic)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()
