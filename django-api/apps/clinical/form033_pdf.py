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


def build_form033_pdf(patient, tenant, form_record, diagnoses, cpo_ceo, professional,
                      indicadores=None, plan_items=None, exams=None,
                      documents=None, consents=None):
    """Devuelve los bytes del PDF del formulario 033 completo del paciente."""
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
    y = _header_band(c, y, width, "DATOS DEL PACIENTE")
    sexo = {"H": "Hombre", "M": "Mujer"}.get(getattr(patient, "sex", ""), "—")
    y = _line(c, y, "Paciente:", patient.full_name, width)
    y = _line(c, y, "Cédula / ID:", patient.national_id, width)
    y = _line(c, y, "Sexo:", sexo, width)
    if getattr(patient, "birth_date", None):
        y = _line(c, y, "F. nacimiento:", str(patient.birth_date), width)

    if form_record:
        # B. Motivo
        y = _header_band(c, y, width, "MOTIVO DE CONSULTA")
        y = _line(c, y, "Motivo:", form_record.motivo_consulta, width)
        if form_record.embarazada is not None:
            y = _line(c, y, "Embarazada:", "Sí" if form_record.embarazada else "No", width)
        # C
        y = _header_band(c, y, width, "ENFERMEDAD ACTUAL")
        y = _line(c, y, "Descripción:", form_record.enfermedad_actual, width)
        # D y E
        pers = [k for k, v in (form_record.antecedentes_personales or {}).items() if v and v.get("checked")]
        fam = [k for k, v in (form_record.antecedentes_familiares or {}).items() if v and v.get("checked")]
        y = _header_band(c, y, width, "ANTECEDENTES PATOLÓGICOS")
        y = _line(c, y, "Personales:", ", ".join(pers) or "Ninguno", width)
        y = _line(c, y, "Familiares:", ", ".join(fam) or "Ninguno", width)
        # F
        y = _header_band(c, y, width, "CONSTANTES VITALES")
        vit = (f"T° {form_record.temperatura or '—'}  ·  Pulso {form_record.pulso or '—'}  ·  "
               f"FR {form_record.frecuencia_respiratoria or '—'}  ·  PA {form_record.presion_arterial or '—'}")
        y = _line(c, y, "Vitales:", vit, width)
        # G
        regiones = [f"{k}: {v}" for k, v in (form_record.examen_estomatognatico or {}).items() if v]
        if regiones:
            y = _header_band(c, y, width, "EXAMEN DEL SISTEMA ESTOMATOGNÁTICO")
            y = _line(c, y, "Hallazgos:", "  ·  ".join(regiones), width)

    # Helper de salto de página: si no queda espacio, cierra la página y abre otra.
    def ensure(space):
        nonlocal y
        if y - space < 22 * mm:
            _footer(c, width)
            c.showPage()
            y = height - 15 * mm

    # I. Indicadores de salud bucal
    if indicadores:
        ensure(40 * mm)
        y = _header_band(c, y, width, "INDICADORES DE SALUD BUCAL")
        hig = indicadores.get("higiene", {})
        placa = sum(int(v.get("placa") or 0) for v in hig.values())
        calc = sum(int(v.get("calculo") or 0) for v in hig.values())
        ging = sum(int(v.get("gingivitis") or 0) for v in hig.values())
        y = _line(c, y, "Higiene oral:", f"Placa {placa}  ·  Cálculo {calc}  ·  Gingivitis {ging}", width)
        y = _line(c, y, "E. periodontal:", (indicadores.get("enfermedad_periodontal") or "—").capitalize(), width)
        y = _line(c, y, "Oclusión:", indicadores.get("oclusion") and f"Angle {indicadores['oclusion']}" or "—", width)
        y = _line(c, y, "Fluorosis:", (indicadores.get("fluorosis") or "—").capitalize(), width)

    # J. Índices CPO-ceo
    ensure(24 * mm)
    y = _header_band(c, y, width, "ÍNDICES CPO-ceo")
    cpo, ceo = cpo_ceo["cpo"], cpo_ceo["ceo"]
    y = _line(c, y, "CPO (perm.):",
              f"C={cpo['C']}  P={cpo['P']}  O={cpo['O']}  TOTAL={cpo['total']}", width)
    y = _line(c, y, "ceo (temp.):",
              f"c={ceo['c']}  e={ceo['e']}  o={ceo['o']}  TOTAL={ceo['total']}", width)

    # Diagnósticos
    if diagnoses:
        ensure(20 * mm + 5 * mm * min(len(diagnoses), 8))
        y = _header_band(c, y, width, "DIAGNÓSTICOS (CIE-10)")
        for d in diagnoses[:12]:
            kind = "DEF" if d.diagnosis_kind == "def" else "PRE"
            pieza = f" [pieza {d.tooth_fdi_code}]" if d.tooth_fdi_code else ""
            y = _line(c, y, f"{d.code or '—'} ({kind}):", f"{d.description}{pieza}", width)

    # Plan de tratamiento
    if plan_items:
        ensure(20 * mm + 5 * mm * min(len(plan_items), 10))
        y = _header_band(c, y, width, "PLAN DE TRATAMIENTO")
        for it in plan_items[:20]:
            pieza = f" [pieza {it['tooth']}]" if it.get("tooth") else ""
            y = _line(c, y, f"{it['status']}:", f"{it['name']}{pieza}", width)

    # Exámenes complementarios
    if exams:
        ensure(20 * mm)
        y = _header_band(c, y, width, "EXÁMENES COMPLEMENTARIOS")
        for ex in exams[:10]:
            informe = f" — Informe: {ex['report']}" if ex.get("report") else " — (sin informe)"
            y = _line(c, y, f"{ex['category']}:", f"{ex['detail']}{informe}", width)

    # Documentos
    if documents:
        ensure(18 * mm)
        y = _header_band(c, y, width, "DOCUMENTOS ADJUNTOS")
        for doc in documents[:15]:
            y = _line(c, y, f"{doc['type']}:", f"{doc['description'] or '—'}  ({doc['date']})", width)

    # Consentimientos
    if consents:
        ensure(18 * mm)
        y = _header_band(c, y, width, "CONSENTIMIENTOS INFORMADOS")
        for co in consents[:10]:
            y = _line(c, y, co["status"] + ":", f"{co['title']}  ({co['date']})", width)

    # Profesional (automático desde la credencial)
    ensure(26 * mm)
    y = _header_band(c, y, width, "PROFESIONAL RESPONSABLE")
    y = _line(c, y, "Profesional:", professional.get("full_name", "—"), width)
    y = _line(c, y, "Registro:", professional.get("license_number") or "—", width)
    y = _line(c, y, "Fecha/hora:", professional.get("recorded_at", "—")[:19].replace("T", " "), width)

    _footer(c, width)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()


def _footer(c, width):
    c.setFont("Helvetica-Oblique", 6)
    c.setFillColor(colors.HexColor("#4c6367"))
    c.drawCentredString(width / 2, 12 * mm,
                        "Documento generado por el sistema de gestión clínica — SNS-MSP / HCU-form.033/2021")
