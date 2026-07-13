"""
Export del formulario MSP HCU-form.033/2021 a PDF (Sprint 25).
Reúne los literales A-P del paciente en un documento imprimible con el
formato oficial del Ministerio de Salud Pública del Ecuador.
"""

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def _header_band(c, y, width, text):
    """Banda de título de literal (fondo lavanda como el formulario oficial)."""
    c.setFillColor(colors.HexColor("#c7c9f0"))
    c.rect(15 * mm, y - 5 * mm, width - 30 * mm, 6 * mm, fill=1, stroke=0)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(17 * mm, y - 3.5 * mm, text)
    return y - 8 * mm


def _line(c, y, label, value, width):
    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(colors.HexColor("#4c6367"))
    c.drawString(17 * mm, y, label)
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.black)
    # Envolver texto largo
    text = str(value or "—")
    max_chars = 95
    lines = [text[i:i + max_chars] for i in range(0, len(text), max_chars)] or ["—"]
    yy = y
    for ln in lines[:4]:
        c.drawString(45 * mm, yy, ln)
        yy -= 4 * mm
    return yy - 1 * mm


def build_form033_pdf(patient, tenant, form_record, diagnoses, cpo_ceo, professional):
    """Devuelve los bytes del PDF del formulario 033 del paciente."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    y = height - 15 * mm

    # Encabezado institucional
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(width / 2, y, tenant.name.upper())
    y -= 5 * mm
    c.setFont("Helvetica", 8)
    c.drawCentredString(width / 2, y, "HISTORIA CLÍNICA ODONTOLÓGICA — SNS-MSP / HCU-form.033/2021")
    y -= 8 * mm

    # A. Datos del paciente
    y = _header_band(c, y, width, "A. DATOS DEL USUARIO / PACIENTE")
    sexo = {"H": "Hombre", "M": "Mujer"}.get(getattr(patient, "sex", ""), "—")
    y = _line(c, y, "Paciente:", patient.full_name, width)
    y = _line(c, y, "Cédula / ID:", patient.national_id, width)
    y = _line(c, y, "Sexo:", sexo, width)
    if getattr(patient, "birth_date", None):
        y = _line(c, y, "F. nacimiento:", str(patient.birth_date), width)

    if form_record:
        # B. Motivo
        y = _header_band(c, y, width, "B. MOTIVO DE CONSULTA")
        y = _line(c, y, "Motivo:", form_record.motivo_consulta, width)
        if form_record.embarazada is not None:
            y = _line(c, y, "Embarazada:", "Sí" if form_record.embarazada else "No", width)
        # C
        y = _header_band(c, y, width, "C. ENFERMEDAD ACTUAL")
        y = _line(c, y, "Descripción:", form_record.enfermedad_actual, width)
        # D y E
        pers = [k for k, v in (form_record.antecedentes_personales or {}).items() if v and v.get("checked")]
        fam = [k for k, v in (form_record.antecedentes_familiares or {}).items() if v and v.get("checked")]
        y = _header_band(c, y, width, "D / E. ANTECEDENTES PATOLÓGICOS")
        y = _line(c, y, "Personales:", ", ".join(pers) or "Ninguno", width)
        y = _line(c, y, "Familiares:", ", ".join(fam) or "Ninguno", width)
        # F
        y = _header_band(c, y, width, "F. CONSTANTES VITALES")
        vit = (f"T° {form_record.temperatura or '—'}  ·  Pulso {form_record.pulso or '—'}  ·  "
               f"FR {form_record.frecuencia_respiratoria or '—'}  ·  PA {form_record.presion_arterial or '—'}")
        y = _line(c, y, "Vitales:", vit, width)
        # G
        regiones = [f"{k}: {v}" for k, v in (form_record.examen_estomatognatico or {}).items() if v]
        if regiones:
            y = _header_band(c, y, width, "G. EXAMEN DEL SISTEMA ESTOMATOGNÁTICO")
            y = _line(c, y, "Hallazgos:", "  ·  ".join(regiones), width)

    # J. Índices CPO-ceo
    y = _header_band(c, y, width, "J. ÍNDICES CPO-ceo")
    cpo, ceo = cpo_ceo["cpo"], cpo_ceo["ceo"]
    y = _line(c, y, "CPO (perm.):",
              f"C={cpo['C']}  P={cpo['P']}  O={cpo['O']}  TOTAL={cpo['total']}", width)
    y = _line(c, y, "ceo (temp.):",
              f"c={ceo['c']}  e={ceo['e']}  o={ceo['o']}  TOTAL={ceo['total']}", width)

    # N. Diagnósticos
    if diagnoses:
        y = _header_band(c, y, width, "N. DIAGNÓSTICOS (CIE-10)")
        for d in diagnoses[:8]:
            kind = "DEF" if d.diagnosis_kind == "def" else "PRE"
            pieza = f" [pieza {d.tooth_fdi_code}]" if d.tooth_fdi_code else ""
            y = _line(c, y, f"{d.code or '—'} ({kind}):", f"{d.description}{pieza}", width)

    # O. Profesional (automático desde la credencial)
    y = _header_band(c, y, width, "O. DATOS DEL PROFESIONAL RESPONSABLE")
    y = _line(c, y, "Profesional:", professional.get("full_name", "—"), width)
    y = _line(c, y, "Registro:", professional.get("license_number") or "—", width)
    y = _line(c, y, "Fecha/hora:", professional.get("recorded_at", "—")[:19].replace("T", " "), width)

    # Pie
    c.setFont("Helvetica-Oblique", 6)
    c.setFillColor(colors.HexColor("#4c6367"))
    c.drawCentredString(width / 2, 12 * mm,
                        "Documento generado por el sistema de gestión clínica — SNS-MSP / HCU-form.033/2021")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()
