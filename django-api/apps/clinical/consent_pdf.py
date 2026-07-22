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

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from apps.clinical.exam_request_pdf import _decode_signature

PETROL = colors.HexColor("#0e5c63")
INK = colors.HexColor("#1f2937")
SOFT = colors.HexColor("#6b7280")
LINE = colors.HexColor("#d1d5db")


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


def build_consent_pdf(clinic, professional, patient, consent):
    """
    clinic:       {name, logo_reader|None, address, phone, email}
    professional: {full_name, specialty, license_number, signature_b64|None}
    patient:      {full_name, national_id, birth_date, age, sex, history_number}
    consent:      {title, procedure, benefits, risks, alternatives, body_text,
                   observations, patient_signature_b64|None, signed_place, signed_date}
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    ml, mr = 20 * mm, width - 20 * mm
    maxw = mr - ml
    y = height - 16 * mm

    def ensure(space):
        nonlocal y
        if y - space < 20 * mm:
            c.showPage()
            y = height - 16 * mm

    # ── Encabezado ──
    logo = clinic.get("logo_reader")
    if logo is not None:
        try:
            c.drawImage(logo, ml, y - 6 * mm, width=24 * mm, height=18 * mm,
                        preserveAspectRatio=True, mask="auto")
        except Exception:
            pass
    tx = ml + (28 * mm if logo is not None else 0)
    c.setFillColor(PETROL)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(tx, y + 6 * mm, clinic.get("name") or "Clínica")
    c.setFillColor(SOFT)
    c.setFont("Helvetica", 8.5)
    ly = y + 1 * mm
    for part in [clinic.get("address"), clinic.get("phone"), clinic.get("email")]:
        if part:
            c.drawString(tx, ly, str(part))
            ly -= 4 * mm
    y -= 22 * mm
    c.setStrokeColor(PETROL)
    c.setLineWidth(1.2)
    c.line(ml, y, mr, y)
    y -= 9 * mm

    # ── Título ──
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(width / 2, y, "CONSENTIMIENTO INFORMADO")
    y -= 6 * mm
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(PETROL)
    y = _wrap(c, consent.get("title"), ml, y, maxw, font="Helvetica-Bold", size=11, leading=5.5)
    y -= 3 * mm

    # ── Paciente y profesional (dos columnas) ──
    def kv(label, value, x, yy):
        c.setFillColor(SOFT)
        c.setFont("Helvetica", 8)
        c.drawString(x, yy, label.upper())
        c.setFillColor(INK)
        c.setFont("Helvetica", 9.5)
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

    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    c.line(ml, y, mr, y)
    y -= 8 * mm

    # ── Secciones del consentimiento ──
    def section(title, text):
        nonlocal y
        if not text:
            return
        ensure(24 * mm)
        c.setFillColor(PETROL)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(ml, y, title.upper())
        y -= 6 * mm
        c.setFillColor(INK)
        y = _wrap(c, text, ml, y, maxw, size=9.5, leading=5)
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
    ensure(56 * mm)
    y = max(y, 60 * mm)
    sign_line_y = y - 24 * mm

    # Firma del paciente (izq)
    psig = _decode_signature(consent.get("patient_signature_b64"))
    if psig is not None:
        try:
            c.drawImage(psig, ml + 4 * mm, sign_line_y + 2 * mm, width=48 * mm, height=20 * mm,
                        preserveAspectRatio=True, mask="auto")
        except Exception:
            pass
    # Firma del profesional (der)
    dsig = _decode_signature(professional.get("signature_b64"))
    if dsig is not None:
        try:
            c.drawImage(dsig, mr - 52 * mm, sign_line_y + 2 * mm, width=48 * mm, height=20 * mm,
                        preserveAspectRatio=True, mask="auto")
        except Exception:
            pass

    c.setStrokeColor(INK)
    c.setLineWidth(0.6)
    c.line(ml, sign_line_y, ml + 60 * mm, sign_line_y)
    c.line(mr - 60 * mm, sign_line_y, mr, sign_line_y)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(ml, sign_line_y - 5 * mm, "Firma del paciente")
    c.drawString(mr - 60 * mm, sign_line_y - 5 * mm, "Firma del profesional")
    c.setFillColor(SOFT)
    c.setFont("Helvetica", 8)
    c.drawString(ml, sign_line_y - 9 * mm, patient.get("full_name") or "")
    c.drawString(mr - 60 * mm, sign_line_y - 9 * mm,
                 f"Reg. {professional.get('license_number') or '—'}")

    # Huella + lugar y fecha
    y = sign_line_y - 20 * mm
    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    c.rect(ml, y - 18 * mm, 24 * mm, 22 * mm)
    c.setFillColor(SOFT)
    c.setFont("Helvetica", 7)
    c.drawCentredString(ml + 12 * mm, y - 21 * mm, "Huella (opcional)")
    c.setFillColor(INK)
    c.setFont("Helvetica", 9.5)
    lugar_fecha = f"Lugar y fecha: {consent.get('signed_place') or '________________'}, {consent.get('signed_date') or '____ / ____ / ______'}"
    c.drawString(ml + 32 * mm, y - 4 * mm, lugar_fecha)

    # ── Pie institucional ──
    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    c.line(ml, 15 * mm, mr, 15 * mm)
    c.setFillColor(SOFT)
    c.setFont("Helvetica", 7)
    footer = " · ".join([p for p in [clinic.get("name"), clinic.get("address"),
                                     clinic.get("phone"), clinic.get("email")] if p])
    c.drawCentredString(width / 2, 10.5 * mm, footer or "")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()
