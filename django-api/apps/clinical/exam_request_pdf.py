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

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

PETROL = colors.HexColor("#0e5c63")
INK = colors.HexColor("#1f2937")
SOFT = colors.HexColor("#6b7280")
LINE = colors.HexColor("#d1d5db")


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


def build_exam_request_pdf(clinic, professional, patient, exam):
    """
    clinic:       {name, logo_reader|None, address, phone, email}
    professional: {full_name, specialty, license_number, signature_b64|None}
    patient:      {full_name, national_id, age, sex, history_number}
    exam:         {datetime, category, detail, justification, observations, priority, urgent}
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    ml, mr = 20 * mm, width - 20 * mm
    y = height - 18 * mm

    # ── Encabezado: logo + datos de la clínica ──
    logo = clinic.get("logo_reader")
    if logo is not None:
        try:
            c.drawImage(logo, ml, y - 6 * mm, width=26 * mm, height=20 * mm,
                        preserveAspectRatio=True, mask="auto")
        except Exception:
            pass
    text_x = ml + (30 * mm if logo is not None else 0)
    c.setFillColor(PETROL)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(text_x, y + 8 * mm, clinic.get("name") or "Clínica")
    c.setFillColor(SOFT)
    c.setFont("Helvetica", 9)
    line_y = y + 3 * mm
    for part in [clinic.get("address"), clinic.get("phone"), clinic.get("email")]:
        if part:
            c.drawString(text_x, line_y, str(part))
            line_y -= 4.5 * mm

    y -= 24 * mm
    c.setStrokeColor(PETROL)
    c.setLineWidth(1.4)
    c.line(ml, y, mr, y)
    y -= 10 * mm

    # ── Título ──
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, y, "SOLICITUD DE EXAMEN COMPLEMENTARIO")
    y -= 4 * mm
    if exam.get("urgent"):
        c.setFillColor(colors.HexColor("#b91c1c"))
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(width / 2, y - 3 * mm, "★ PRIORIDAD URGENTE")
        y -= 7 * mm
    y -= 6 * mm

    # ── Helper de secciones ──
    def section(title):
        nonlocal y
        c.setFillColor(PETROL)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(ml, y, title.upper())
        c.setStrokeColor(LINE)
        c.setLineWidth(0.5)
        c.line(ml, y - 2 * mm, mr, y - 2 * mm)
        y -= 8 * mm

    def field(label, value, x=None, inline=False):
        nonlocal y
        xx = x if x is not None else ml
        c.setFillColor(SOFT)
        c.setFont("Helvetica", 8.5)
        c.drawString(xx, y, label.upper())
        c.setFillColor(INK)
        c.setFont("Helvetica", 10.5)
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
        c.setFillColor(SOFT)
        c.setFont("Helvetica", 8.5)
        c.drawString(ml, y, label.upper())
        y -= 5 * mm
        c.setFillColor(INK)
        c.setFont("Helvetica", 10)
        # Envoltura simple de texto
        words = str(text or "—").split()
        line, maxw = "", mr - ml
        for w in words:
            test = f"{line} {w}".strip()
            if c.stringWidth(test, "Helvetica", 10) > maxw:
                c.drawString(ml, y, line)
                y -= 5 * mm
                line = w
            else:
                line = test
        c.drawString(ml, y, line)
        y -= 9 * mm

    paragraph("Motivo / justificación clínica", exam.get("justification"))
    if exam.get("observations"):
        paragraph("Observaciones", exam.get("observations"))

    # ── Firma y sello ──
    y = max(y, 60 * mm)
    sign_y = 48 * mm
    sig = _decode_signature(professional.get("signature_b64"))
    if sig is not None:
        try:
            c.drawImage(sig, width / 2 - 30 * mm, sign_y, width=60 * mm, height=22 * mm,
                        preserveAspectRatio=True, mask="auto")
        except Exception:
            pass
    c.setStrokeColor(INK)
    c.setLineWidth(0.6)
    c.line(width / 2 - 40 * mm, sign_y, width / 2 + 40 * mm, sign_y)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(width / 2, sign_y - 5 * mm, professional.get("full_name") or "")
    c.setFillColor(SOFT)
    c.setFont("Helvetica", 8.5)
    c.drawCentredString(width / 2, sign_y - 9.5 * mm,
                        f"Firma y sello · Reg. {professional.get('license_number') or '—'}")

    # ── Pie institucional ──
    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    c.line(ml, 16 * mm, mr, 16 * mm)
    c.setFillColor(SOFT)
    c.setFont("Helvetica", 7.5)
    footer = " · ".join([p for p in [clinic.get("name"), clinic.get("address"),
                                     clinic.get("phone"), clinic.get("email")] if p])
    c.drawCentredString(width / 2, 11 * mm, footer or "")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()
