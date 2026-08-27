"""
Motor global de estilos de documentos (Sprint 60).
────────────────────────────────────────────────────────────────────────
Punto ÚNICO por el que cualquier generador obtiene la apariencia de un
documento: colores, tipografías, márgenes, tamaño de hoja, tablas,
encabezado, pie, logotipo, firma y marca de agua.

Antes cada generador llevaba sus propios colores y medidas escritos a
mano (`PETROL = HexColor("#0e5c63")` repetido en varios archivos), de
modo que cambiar la identidad de una clínica obligaba a tocar código y
los documentos no se parecían entre sí. Ahora la apariencia se configura
una vez por clínica y todos los documentos la siguen.

CÓMO SE USA DESDE UN GENERADOR

    from apps.common.document_style import get_document_style

    style = get_document_style(tenant)
    c = canvas.Canvas(buf, pagesize=style.page_size)
    y = style.draw_header(c, clinic=..., professional=...)
    ...
    style.draw_footer(c, page_number=1)

El generador no decide colores ni márgenes: los pide. Un documento nuevo
que use `get_document_style` queda integrado en el sistema sin trabajo
adicional, que es el requisito de que la configuración alcance también a
los documentos futuros.

EXCEPCIÓN DELIBERADA
El formulario MSP HCU-033/2021 (`apps/clinical/form033_pdf.py` y
`form033_xlsx.py`) NO usa este motor. Es un formato oficial del
Ministerio con un diseño legalmente fijado; personalizarlo lo
invalidaría como documento oficial.

COMPATIBILIDAD
Si una clínica no ha configurado nada, `get_document_style` devuelve el
estilo por defecto, que reproduce el aspecto que ya tenían los
documentos. Ningún documento existente cambia hasta que alguien toca la
configuración.
"""

from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, LEGAL, LETTER, landscape
from reportlab.lib.units import mm

_PAGE_SIZES = {"A4": A4, "LETTER": LETTER, "LEGAL": LEGAL}

# Familias tipográficas incorporadas en reportlab. No se admiten fuentes
# arbitrarias porque habría que registrar el .ttf y distribuirlo; las
# incorporadas cubren serif, sans y monoespaciada sin dependencias.
_FONT_FAMILIES = {
    "Helvetica": ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique"),
    "Times": ("Times-Roman", "Times-Bold", "Times-Italic"),
    "Courier": ("Courier", "Courier-Bold", "Courier-Oblique"),
}

_FALLBACK_PRIMARY = "#0e5c63"


def _color(value, fallback):
    """Convierte '#rrggbb' en un color de reportlab, con reserva."""
    try:
        if value:
            return colors.HexColor(value)
    except Exception:
        pass
    return colors.HexColor(fallback)


class DocumentStyle:
    """
    Apariencia ya resuelta y lista para dibujar. Se construye una vez por
    documento; no consulta la base de datos.
    """

    def __init__(self, settings, brand=None):
        self.s = settings
        self.brand = brand or {}

        page = settings["page"]
        size = _PAGE_SIZES.get(str(page.get("size", "A4")).upper(), A4)
        self.page_size = landscape(size) if page.get("orientation") == "landscape" else size
        self.width, self.height = self.page_size

        self.margin_top = float(page.get("margin_top_mm", 20)) * mm
        self.margin_bottom = float(page.get("margin_bottom_mm", 18)) * mm
        self.margin_left = float(page.get("margin_left_mm", 20)) * mm
        self.margin_right = float(page.get("margin_right_mm", 20)) * mm
        self.block_spacing = float(page.get("block_spacing_mm", 5)) * mm

        fam = _FONT_FAMILIES.get(settings["typography"].get("family"), _FONT_FAMILIES["Helvetica"])
        self.font, self.font_bold, self.font_italic = fam
        self.size = float(settings["typography"].get("size_pt", 10))
        self.leading = self.size * float(settings["typography"].get("line_height", 1.35))
        self.title_size = float(settings["typography"].get("title_size_pt", 16))
        self.subtitle_size = float(settings["typography"].get("subtitle_size_pt", 12))

        pal = settings["palette"]
        # El color primario vacío hereda la marca de la clínica: la
        # identidad visual se define en un solo sitio.
        self.primary = _color(pal.get("primary") or self.brand.get("primary"), _FALLBACK_PRIMARY)
        self.secondary = _color(pal.get("secondary"), "#6b7280")
        self.accent = _color(pal.get("accent"), _FALLBACK_PRIMARY)
        self.title_color = _color(pal.get("title"), "#111827")
        self.subtitle_color = _color(pal.get("subtitle"), "#374151")
        self.ink = _color(settings["typography"].get("color"), "#1f2937")
        self.separator = _color(pal.get("separator"), "#d1d5db")
        self.alert = _color(pal.get("alert"), "#b91c1c")
        self.highlight = _color(pal.get("highlight"), "#fef3c7")
        self.icon = _color(pal.get("icon"), _FALLBACK_PRIMARY)

    # ── Medidas útiles ────────────────────────────────────────────────
    @property
    def content_left(self):
        return self.margin_left

    @property
    def content_right(self):
        return self.width - self.margin_right

    @property
    def content_width(self):
        return self.content_right - self.content_left

    # ── Encabezado ────────────────────────────────────────────────────
    def draw_header(self, c, clinic=None, professional=None):
        """
        Dibuja el encabezado y devuelve la Y donde puede empezar el
        contenido. Si está desactivado no dibuja nada y devuelve el borde
        superior del área de contenido.
        """
        h = self.s["header"]
        top = self.height - self.margin_top
        if not h.get("enabled", True):
            return top

        clinic = clinic or {}
        professional = professional or {}
        lg = self.s["logo"]
        height = float(h.get("height_mm", 26)) * mm

        bg = h.get("background")
        if bg:
            c.setFillColor(_color(bg, "#ffffff"))
            c.rect(0, top - height, self.width, height, stroke=0, fill=1)

        text_color = _color(h.get("text_color") or None, "#1f2937") if h.get("text_color") \
            else self.primary

        x = self.content_left
        logo = clinic.get("logo_reader") if h.get("show_logo", True) else None
        if logo is not None:
            lw = float(lg.get("width_mm", 26)) * mm
            lh = float(lg.get("height_mm", 20)) * mm
            pos = lg.get("position", "header_left")
            lx = x
            if pos == "header_center":
                lx = (self.width - lw) / 2
            elif pos == "header_right":
                lx = self.content_right - lw
            try:
                c.saveState()
                opacity = float(lg.get("opacity", 1.0))
                if opacity < 1:
                    c.setFillAlpha(opacity)
                c.drawImage(logo, lx, top - lh, width=lw, height=lh,
                            preserveAspectRatio=True, mask="auto")
                c.restoreState()
            except Exception:
                pass       # un logotipo ilegible nunca debe romper el documento
            if pos == "header_left":
                x += lw + float(lg.get("gap_mm", 4)) * mm

        align = h.get("align", "left")

        def put(text, size, bold, color, dy):
            if not text:
                return 0
            c.setFont(self.font_bold if bold else self.font, size)
            c.setFillColor(color)
            if align == "center":
                c.drawCentredString(self.width / 2, dy, text)
            elif align == "right":
                c.drawRightString(self.content_right, dy, text)
            else:
                c.drawString(x, dy, text)
            return 1

        y = top - 5 * mm
        if h.get("show_clinic_name", True) and clinic.get("name"):
            put(clinic["name"], self.subtitle_size + 2, True, text_color, y)
            y -= self.subtitle_size + 3

        if h.get("show_professional", True) and professional.get("full_name"):
            extra = []
            if h.get("show_specialty", True) and professional.get("specialty"):
                extra.append(professional["specialty"])
            label = professional["full_name"] + (f" · {' · '.join(extra)}" if extra else "")
            put(label, self.size, False, self.secondary, y)
            y -= self.size + 2

        contact = []
        if h.get("show_address", True) and clinic.get("address"):
            contact.append(clinic["address"])
        if h.get("show_phone", True) and clinic.get("phone"):
            contact.append(f"Tel. {clinic['phone']}")
        if h.get("show_email", True) and clinic.get("email"):
            contact.append(clinic["email"])
        if h.get("show_website", False) and clinic.get("website"):
            contact.append(clinic["website"])
        if contact:
            put(" · ".join(contact), self.size - 1.5, False, self.secondary, y)
            y -= self.size

        line_y = top - height
        c.setStrokeColor(self.separator)
        c.setLineWidth(0.8)
        c.line(self.content_left, line_y, self.content_right, line_y)
        return line_y - self.block_spacing

    # ── Pie ───────────────────────────────────────────────────────────
    def draw_footer(self, c, page_number=None, total_pages=None):
        f = self.s["footer"]
        if not f.get("enabled", True):
            return
        y = self.margin_bottom
        c.setStrokeColor(self.separator)
        c.setLineWidth(0.6)
        c.line(self.content_left, y + 6 * mm, self.content_right, y + 6 * mm)

        bits = []
        if f.get("text"):
            bits.append(f["text"])
        if f.get("show_date", True):
            now = datetime.now()
            bits.append(now.strftime("%d/%m/%Y %H:%M") if f.get("show_time")
                        else now.strftime("%d/%m/%Y"))
        if f.get("show_page_numbers", True) and page_number:
            bits.append(f"Página {page_number}" + (f" de {total_pages}" if total_pages else ""))

        color = _color(f.get("text_color") or None, "#6b7280") if f.get("text_color") \
            else self.secondary
        c.setFont(self.font, self.size - 2)
        c.setFillColor(color)
        text = "  ·  ".join(bits)
        align = f.get("align", "center")
        if text:
            if align == "left":
                c.drawString(self.content_left, y, text)
            elif align == "right":
                c.drawRightString(self.content_right, y, text)
            else:
                c.drawCentredString(self.width / 2, y, text)
        if f.get("legal_text"):
            c.setFont(self.font, self.size - 3)
            c.drawCentredString(self.width / 2, y - 4 * mm, f["legal_text"])

    # ── Marca de agua ─────────────────────────────────────────────────
    def draw_watermark(self, c):
        w = self.s["watermark"]
        if not w.get("enabled") or not w.get("text"):
            return
        try:
            c.saveState()
            c.setFillColor(self.secondary)
            c.setFillAlpha(float(w.get("opacity", 0.08)))
            c.setFont(self.font_bold, float(w.get("size_pt", 60)))
            c.translate(self.width / 2, self.height / 2)
            c.rotate(float(w.get("rotation", 45)))
            c.drawCentredString(0, 0, w["text"])
            c.restoreState()
        except Exception:
            pass       # la marca de agua jamás debe impedir emitir el documento

    # ── Soporte para generadores con Platypus ─────────────────────────
    #
    # El sistema tiene generadores de los dos estilos de reportlab: unos
    # dibujan sobre el canvas (solicitudes, consentimientos) y otros
    # componen con flowables (historia clínica). El motor sirve a ambos,
    # o los que usan Platypus se quedarían fuera de la configuración.

    def platypus_doc(self, buffer, title=""):
        """SimpleDocTemplate con la hoja y los márgenes configurados."""
        from reportlab.platypus import SimpleDocTemplate

        return SimpleDocTemplate(
            buffer, pagesize=self.page_size,
            leftMargin=self.margin_left, rightMargin=self.margin_right,
            topMargin=self.margin_top, bottomMargin=self.margin_bottom,
            title=title or "",
        )

    def paragraph_styles(self):
        """Hoja de estilos de párrafo con la tipografía y la paleta configuradas."""
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

        ss = getSampleStyleSheet()
        ss.add(ParagraphStyle(
            name="DocTitle", parent=ss["Title"], fontName=self.font_bold,
            fontSize=self.title_size, leading=self.title_size * 1.2,
            textColor=self.title_color, spaceAfter=10,
        ))
        ss.add(ParagraphStyle(
            name="DocHeading", parent=ss["Heading2"], fontName=self.font_bold,
            fontSize=self.subtitle_size, leading=self.subtitle_size * 1.25,
            textColor=self.subtitle_color, spaceBefore=8, spaceAfter=4,
        ))
        ss.add(ParagraphStyle(
            name="DocBody", parent=ss["Normal"], fontName=self.font,
            fontSize=self.size, leading=self.leading, textColor=self.ink,
        ))
        ss.add(ParagraphStyle(
            name="DocSmall", parent=ss["Normal"], fontName=self.font,
            fontSize=max(6, self.size - 2.5), leading=self.leading * 0.85,
            textColor=self.secondary,
        ))
        return ss

    def page_furniture(self, clinic=None, professional=None):
        """
        Callback `onPage` para Platypus: dibuja marca de agua y pie en cada
        página. El encabezado de estos documentos va como contenido (ver
        `header_flowables`), porque en Platypus dibujarlo aquí se solaparía
        con el texto salvo reservando margen a mano.
        """
        def draw(c, doc):
            self.draw_watermark(c)
            self.draw_footer(c, page_number=doc.page)
        return draw

    def header_flowables(self, clinic=None, professional=None):
        """Encabezado como contenido, para los documentos compuestos con Platypus."""
        from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle

        h = self.s["header"]
        if not h.get("enabled", True):
            return []
        clinic = clinic or {}
        professional = professional or {}
        ss = self.paragraph_styles()

        lines = []
        if h.get("show_clinic_name", True) and clinic.get("name"):
            lines.append(f'<font color="{self.primary.hexval().replace("0x", "#")}">'
                         f'<b>{clinic["name"]}</b></font>')
        if h.get("show_professional", True) and professional.get("full_name"):
            bits = [professional["full_name"]]
            if h.get("show_specialty", True) and professional.get("specialty"):
                bits.append(professional["specialty"])
            lines.append(" · ".join(bits))
        contact = [clinic.get(k) for k, flag in
                   (("address", "show_address"), ("phone", "show_phone"),
                    ("email", "show_email"), ("website", "show_website"))
                   if h.get(flag, True) and clinic.get(k)]
        if contact:
            lines.append(" · ".join(str(x) for x in contact))
        text = Paragraph("<br/>".join(lines), ss["DocSmall"]) if lines else Paragraph("", ss["DocSmall"])

        lg = self.s["logo"]
        logo = clinic.get("logo_reader") if h.get("show_logo", True) else None
        if logo is not None:
            try:
                img = Image(logo, width=float(lg.get("width_mm", 26)) * mm,
                            height=float(lg.get("height_mm", 20)) * mm, kind="proportional")
                row = [[img, text]]
                widths = [float(lg.get("width_mm", 26)) * mm + float(lg.get("gap_mm", 4)) * mm, None]
            except Exception:
                row, widths = [[text]], [None]
        else:
            row, widths = [[text]], [None]

        table = Table(row, colWidths=widths, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, 0), (-1, -1), 0.8, self.separator),
        ]))
        return [table, Spacer(1, self.block_spacing)]

    # ── Tablas ────────────────────────────────────────────────────────
    def table_style(self, header_rows=1):
        """TableStyle de reportlab con la configuración de la clínica."""
        from reportlab.platypus import TableStyle

        t = self.s["tables"]
        pal = self.s["palette"]
        header_bg = _color(t.get("header_bg") or pal.get("table_header_bg"), _FALLBACK_PRIMARY)
        header_text = _color(pal.get("table_header_text"), "#ffffff")
        border = _color(t.get("border_color") or pal.get("separator"), "#d1d5db")
        pad = float(t.get("cell_padding_mm", 2)) * mm

        cmds = [
            ("FONTNAME", (0, 0), (-1, header_rows - 1), self.font_bold),
            ("FONTNAME", (0, header_rows), (-1, -1), self.font),
            ("FONTSIZE", (0, 0), (-1, -1), self.size - 1),
            ("TEXTCOLOR", (0, 0), (-1, header_rows - 1), header_text),
            ("TEXTCOLOR", (0, header_rows), (-1, -1), self.ink),
            ("LEFTPADDING", (0, 0), (-1, -1), pad),
            ("RIGHTPADDING", (0, 0), (-1, -1), pad),
            ("TOPPADDING", (0, 0), (-1, -1), pad * 0.6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), pad * 0.6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
        if t.get("shaded", True):
            cmds.append(("BACKGROUND", (0, 0), (-1, header_rows - 1), header_bg))
        if float(t.get("border_width", 0.6)) > 0:
            cmds.append(("GRID", (0, 0), (-1, -1), float(t.get("border_width", 0.6)), border))
        if t.get("zebra", True):
            cmds.append(("ROWBACKGROUNDS", (0, header_rows), (-1, -1),
                         [colors.white, _color(t.get("zebra_color"), "#f9fafb")]))
        return TableStyle(cmds)


def default_settings():
    """Apariencia por defecto, sin tocar la base de datos."""
    from apps.configuration.models import DocumentAppearance

    return {g: DocumentAppearance.DEFAULTS[g]() for g in DocumentAppearance.GROUPS}


def get_document_style(tenant=None, brand=None):
    """
    Estilo de documentos de una clínica. Si no hay tenant o no hay
    configuración guardada, devuelve el estilo por defecto: los
    documentos siguen saliendo exactamente como antes.
    """
    settings = default_settings()
    if tenant is not None:
        try:
            from apps.configuration.models import DocumentAppearance

            row = DocumentAppearance.objects.filter(tenant=tenant).first()
            if row is not None:
                settings = row.resolved()
        except Exception:
            pass       # la configuración nunca debe impedir emitir un documento

    if brand is None and tenant is not None:
        brand = _brand_of(tenant)
    return DocumentStyle(settings, brand=brand)


def _brand_of(tenant):
    """Color de marca de la clínica, para heredarlo cuando la paleta lo deja vacío."""
    try:
        from apps.configuration.models import ClinicBranding

        row = ClinicBranding.objects.filter(tenant=tenant).first()
        if row and isinstance(row.theme, dict):
            return {"primary": row.theme.get("primary") or ""}
    except Exception:
        pass
    return {}
