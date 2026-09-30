
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

import logging
from datetime import date, datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, A5, LEGAL, LETTER, landscape
from reportlab.lib.units import mm

logger = logging.getLogger("apps.documentos")

_PAGE_SIZES = {"A4": A4, "LETTER": LETTER, "LEGAL": LEGAL, "A5": A5}

# Equivalentes de las familias de reportlab en las hojas de cálculo.
_XLSX_FONTS = {"Helvetica": "Arial", "Times": "Times New Roman", "Courier": "Courier New"}

# Familias tipográficas incorporadas en reportlab. No se admiten fuentes
# arbitrarias porque habría que registrar el .ttf y distribuirlo; las
# incorporadas cubren serif, sans y monoespaciada sin dependencias.
_FONT_FAMILIES = {
    "Helvetica": ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique"),
    "Times": ("Times-Roman", "Times-Bold", "Times-Italic"),
    "Courier": ("Courier", "Courier-Bold", "Courier-Oblique"),
}

_FALLBACK_PRIMARY = "#0e5c63"


def ahora_local():
    """Fecha y hora en la zona de la clínica (TIME_ZONE), sin tzinfo."""
    from django.utils import timezone

    return timezone.localtime().replace(tzinfo=None)


def fecha_documento(valor, con_hora=False):
    """
    Una fecha como se escribe en un documento: 30/09/2026 (y la hora si
    se pide). Acepta date, datetime (con o sin zona) o texto ISO, y deja
    tal cual cualquier otro texto. Los documentos mezclaban 2026-09-30,
    30/09/2026 y horas en UTC.
    """
    from django.utils import timezone

    if valor in (None, ""):
        return "—"
    if isinstance(valor, str):
        try:
            valor = datetime.fromisoformat(valor) if ("T" in valor or " " in valor) \
                else date.fromisoformat(valor)
        except ValueError:
            return valor
    if isinstance(valor, datetime):
        if timezone.is_aware(valor):
            valor = timezone.localtime(valor)
        return valor.strftime("%d/%m/%Y %H:%M" if con_hora else "%d/%m/%Y")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    return str(valor)


def ajustar(c, texto, fuente, cuerpo, ancho):
    """Parte un texto en líneas que caben en `ancho`, respetando sus saltos."""
    lineas = []
    for parrafo in str(texto or "").splitlines() or [""]:
        actual = ""
        for palabra in parrafo.split():
            prueba = f"{actual} {palabra}".strip()
            if actual and c.stringWidth(prueba, fuente, cuerpo) > ancho:
                lineas.append(actual)
                actual = palabra
            else:
                actual = prueba
        lineas.append(actual)
    return lineas


def recortar(c, texto, fuente, cuerpo, ancho):
    """El texto en una línea; si no cabe, cortado con «…»."""
    texto = str(texto)
    if c.stringWidth(texto, fuente, cuerpo) <= ancho:
        return texto
    while texto and c.stringWidth(texto + "…", fuente, cuerpo) > ancho:
        texto = texto[:-1]
    return texto.rstrip() + "…"


def _esc(texto):
    """Escapa un texto para meterlo en un Paragraph de reportlab."""
    from xml.sax.saxutils import escape

    return escape(str(texto))


def _color(value, fallback):
    """
    Convierte '#rrggbb' en un color de reportlab, con reserva.

    Este SÍ se queda callado, y es una decisión: se llama decenas de
    veces por página, así que registrar cada color mal escrito llenaría
    el registro de ruido para decir siempre lo mismo. Además tiene una
    reserva definida, de modo que el resultado es correcto y no una
    aproximación. Lo que sí deja rastro es leer la configuración entera,
    que es donde ese color se escribió mal.
    """
    try:
        if value:
            return colors.HexColor(value)
    except Exception:
        # Callado a propósito, por lo que explica el docstring: esto se
        # llama decenas de veces por página y tiene una reserva definida.
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
                # El documento sale igual, que es lo correcto. Pero la
                # clínica que subió su logotipo y no lo ve en ninguna
                # receta merece que alguien pueda averiguar por qué.
                logger.warning(
                    "No se pudo dibujar el logotipo de la clínica",
                    exc_info=True,
                )
            if pos == "header_left":
                x += lw + float(lg.get("gap_mm", 4)) * mm

        align = h.get("align", "left")

        # Qué líneas lleva, para centrarlas en la altura del membrete. Antes
        # empezaban arriba del todo y dejaban un hueco en blanco bajo el
        # texto, que es lo primero que se ve de cada documento.
        lineas = []
        if h.get("show_clinic_name", True) and clinic.get("name"):
            lineas.append(self.subtitle_size + 3)
        if h.get("show_professional", True) and professional.get("full_name"):
            lineas.append(self.size + 2)
        if any(h.get(k, d) and clinic.get(v) for k, v, d in (
                ("show_address", "address", True), ("show_phone", "phone", True),
                ("show_email", "email", True), ("show_website", "website", False))):
            lineas.append(self.size)
        alto_texto = sum(lineas)

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

        y = top - max(4 * mm, (height - alto_texto) / 2) - (self.subtitle_size if lineas else 0) * 0.75
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

        # Filete doble: grueso del color de la clínica y fino gris debajo,
        # el remate habitual de un membrete formal.
        line_y = top - height
        c.setStrokeColor(self.primary)
        c.setLineWidth(1.4)
        c.line(self.content_left, line_y, self.content_right, line_y)
        c.setStrokeColor(self.separator)
        c.setLineWidth(0.5)
        c.line(self.content_left, line_y - 1.2 * mm, self.content_right, line_y - 1.2 * mm)
        return line_y - 1.2 * mm - self.block_spacing

    # ── Pie ───────────────────────────────────────────────────────────
    def draw_footer(self, c, page_number=None, total_pages=None, clinic=None):
        f = self.s["footer"]
        if not f.get("enabled", True):
            return
        y = self.margin_bottom
        c.setStrokeColor(self.separator)
        c.setLineWidth(0.6)
        c.line(self.content_left, y + 6 * mm, self.content_right, y + 6 * mm)

        bits = []
        # El pie institucional (nombre, dirección, teléfono) lo escribía
        # cada generador por su cuenta; ahora sale de aquí, de modo que
        # todos los documentos lo muestran igual y se puede desactivar.
        if f.get("show_clinic", True) and clinic:
            bits += [str(clinic[k]) for k in ("name", "address", "phone", "email")
                     if clinic.get(k)]
        if f.get("text"):
            bits.append(f["text"])
        if f.get("show_date", True):
            # Hora de la clínica, no la del servidor: en un contenedor en
            # UTC, `datetime.now()` fechaba las recetas de la tarde en
            # Ecuador con el día siguiente.
            now = ahora_local()
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
            # Callado a propósito: una marca de agua ausente es un detalle
            # estético que no cambia lo que el documento dice ni quién lo
            # firma. A diferencia del logotipo o de la firma, nadie va a
            # preguntarse por qué falta.
            pass

    # ── Piezas de los documentos formales ─────────────────────────────
    #
    # Título, secciones y cuadros de datos iguales en todos los
    # documentos. Antes cada generador dibujaba los suyos —títulos
    # centrados en unos y a la derecha en otros, datos sueltos sin
    # recuadro— y los documentos de la misma clínica no se parecían.

    def draw_title_block(self, c, y, title, subtitle=None, meta=None):
        """
        Título del documento a la izquierda y, a la derecha, sus datos de
        control (número, fecha…). Debajo, un filete del color principal.
        Devuelve la Y donde sigue el contenido.

        meta: lista de (etiqueta, valor).
        """
        meta = [(k, v) for k, v in (meta or []) if v not in (None, "")]
        ancho_meta = 0
        for k, v in meta:
            ancho_meta = max(ancho_meta, c.stringWidth(f"{k}  ", self.font, self.size - 2)
                             + c.stringWidth(str(v), self.font_bold, self.size - 1))
        ancho_titulo = self.content_width - ancho_meta - (6 * mm if meta else 0)

        cuerpo = self.title_size - 2
        c.setFillColor(self.title_color)
        c.setFont(self.font_bold, cuerpo)
        lineas = ajustar(c, title.upper(), self.font_bold, cuerpo, ancho_titulo)
        yy = y - cuerpo * 0.8
        for linea in lineas:
            c.drawString(self.content_left, yy, linea)
            yy -= cuerpo * 1.15
        if subtitle:
            c.setFillColor(self.primary)
            c.setFont(self.font_bold, self.size + 0.5)
            for linea in ajustar(c, subtitle, self.font_bold, self.size + 0.5, ancho_titulo):
                c.drawString(self.content_left, yy + 1 * mm, linea)
                yy -= self.size * 1.3
        alto_izq = y - yy

        ym = y - (self.size - 1) * 0.9
        for k, v in meta:
            c.setFillColor(self.secondary)
            c.setFont(self.font, self.size - 2)
            ancho_v = c.stringWidth(str(v), self.font_bold, self.size - 1)
            c.drawRightString(self.content_right - ancho_v - 1.5 * mm, ym, k)
            c.setFillColor(self.ink)
            c.setFont(self.font_bold, self.size - 1)
            c.drawRightString(self.content_right, ym, str(v))
            ym -= self.size + 2
        alto_der = y - ym

        base = y - max(alto_izq, alto_der) - 1 * mm
        c.setStrokeColor(self.primary)
        c.setLineWidth(1)
        c.line(self.content_left, base, self.content_right, base)
        return base - self.block_spacing - 1 * mm

    def draw_section(self, c, y, text, number=None):
        """Encabezado de sección: banda suave con una barra del color principal."""
        alto = self.size + 5
        c.saveState()
        c.setFillColor(self.primary)
        c.setFillAlpha(0.08)
        c.rect(self.content_left, y - alto, self.content_width, alto, stroke=0, fill=1)
        c.restoreState()
        c.setFillColor(self.primary)
        c.rect(self.content_left, y - alto, 1.2 * mm, alto, stroke=0, fill=1)
        c.setFont(self.font_bold, self.size - 0.5)
        etiqueta = f"{number}. {text}" if number else text
        c.drawString(self.content_left + 3.5 * mm, y - alto + (alto - self.size) / 2 + 1.2,
                     etiqueta.upper())
        return y - alto - 3 * mm

    def draw_fields(self, c, y, filas, columnas=None):
        """
        Datos en una cuadrícula con bordes: cada celda lleva su etiqueta
        pequeña y el valor debajo. Es la forma de un formulario formal y
        se lee de un vistazo, a diferencia de pares sueltos en la página.

        filas: lista de filas; cada fila, lista de (etiqueta, valor) o
        (etiqueta, valor, columnas_que_ocupa). Devuelve la Y de debajo.
        """
        columnas = columnas or max(sum(celda[2] if len(celda) > 2 else 1 for celda in fila)
                                   for fila in filas)
        ancho_col = self.content_width / columnas
        alto = self.size * 2.6 + 2
        top = y
        c.setLineWidth(0.5)
        c.setStrokeColor(self.separator)
        for fila in filas:
            x = self.content_left
            for celda in fila:
                etiqueta, valor = celda[0], celda[1]
                ocupa = celda[2] if len(celda) > 2 else 1
                ancho = ancho_col * ocupa
                c.rect(x, y - alto, ancho, alto, stroke=1, fill=0)
                c.setFillColor(self.secondary)
                c.setFont(self.font, self.size - 3)
                c.drawString(x + 2 * mm, y - (self.size - 3) - 1.6 * mm, str(etiqueta).upper())
                c.setFillColor(self.ink)
                c.setFont(self.font, self.size - 0.5)
                texto = "—" if valor in (None, "") else str(valor)
                c.drawString(x + 2 * mm, y - alto + 2.2 * mm,
                             recortar(c, texto, self.font, self.size - 0.5, ancho - 4 * mm))
                x += ancho
            y -= alto
        # Borde exterior algo más marcado que las divisiones interiores.
        c.setLineWidth(0.8)
        c.rect(self.content_left, y, self.content_width, top - y, stroke=1, fill=0)
        return y - self.block_spacing

    # ── Firmas ────────────────────────────────────────────────────────
    def draw_signature(self, c, y, slots):
        """
        Dibuja uno o varios bloques de firma y devuelve la Y por debajo.

        `slots` es una lista de diccionarios
        {caption, full_name, license_number, specialty, image}. Con un
        solo bloque se respeta `signature.position`; con dos o más se
        reparten a lo ancho del contenido, que es lo que necesita el
        consentimiento (paciente y profesional).

        Antes cada generador dibujaba su propia línea de firma con
        medidas y colores escritos a mano, así que la firma era lo único
        del documento que no seguía la configuración de la clínica.
        """
        sg = self.s["signature"]
        slots = [s for s in slots if s]
        if not slots:
            return y

        iw = float(sg.get("width_mm", 45)) * mm
        ih = float(sg.get("height_mm", 18)) * mm
        line_w = max(iw + 15 * mm, 55 * mm)
        if len(slots) > 1:
            line_w = min(line_w, (self.content_width - 10 * mm) / len(slots))
            gap = (self.content_width - line_w * len(slots)) / (len(slots) - 1)
            xs = [self.content_left + i * (line_w + gap) for i in range(len(slots))]
        else:
            pos = sg.get("position", "right")
            if pos == "left":
                x0 = self.content_left
            elif pos == "center":
                x0 = self.content_left + (self.content_width - line_w) / 2
            else:
                x0 = self.content_right - line_w
            xs = [x0]

        line_y = y - ih - 2 * mm
        lowest = line_y
        for x0, slot in zip(xs, slots):
            if sg.get("show_image", True) and slot.get("image") is not None:
                try:
                    c.drawImage(slot["image"], x0 + (line_w - iw) / 2, line_y + 1.5 * mm,
                                width=iw, height=ih, preserveAspectRatio=True, mask="auto")
                except Exception:
                    # Que el documento salga es lo correcto; que salga SIN
                    # LA FIRMA del profesional y sin que nadie se entere,
                    # no. Una receta sin firma es otro documento.
                    logger.warning(
                        "No se pudo estampar la firma en el documento",
                        exc_info=True,
                    )
            c.setStrokeColor(self.ink)
            c.setLineWidth(0.6)
            c.line(x0, line_y, x0 + line_w, line_y)

            rows = []
            if slot.get("caption"):
                rows.append((True, slot["caption"]))
            if sg.get("show_name", True) and slot.get("full_name"):
                rows.append((not slot.get("caption"), slot["full_name"]))
            detail = []
            if sg.get("show_specialty", True) and slot.get("specialty"):
                detail.append(str(slot["specialty"]))
            if sg.get("show_license", True) and slot.get("license_number"):
                detail.append(f"Reg. {slot['license_number']}")
            if detail:
                rows.append((False, " · ".join(detail)))

            ty = line_y - 5 * mm
            for bold, text in rows:
                c.setFont(self.font_bold if bold else self.font,
                          self.size - (0.5 if bold else 1.5))
                c.setFillColor(self.ink if bold else self.secondary)
                c.drawCentredString(x0 + line_w / 2, ty, text)
                ty -= self.size + 1
            lowest = min(lowest, ty)
        return lowest - 2 * mm

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

    def page_furniture(self, clinic=None, professional=None, total_pages=None):
        """
        Callback `onPage` para Platypus: dibuja marca de agua y pie en cada
        página. El encabezado de estos documentos va como contenido (ver
        `header_flowables`), porque en Platypus dibujarlo aquí se solaparía
        con el texto salvo reservando margen a mano.
        """
        def draw(c, doc):
            self.draw_watermark(c)
            self.draw_footer(c, page_number=doc.page, total_pages=total_pages, clinic=clinic)
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
            # Mismo cuerpo que el membrete del canvas: antes aquí el nombre
            # de la clínica salía en letra de nota al pie.
            lines.append(f'<font color="{self.primary.hexval().replace("0x", "#")}" '
                         f'size="{self.subtitle_size + 2}"><b>{_esc(clinic["name"])}</b></font>')
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
        from reportlab.lib.styles import ParagraphStyle

        membrete = ParagraphStyle("membrete", parent=ss["DocSmall"], fontSize=self.size - 1,
                                  leading=self.size + 3, textColor=self.secondary)
        text = Paragraph("<br/>".join(lines), membrete) if lines else Paragraph("", membrete)

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
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LINEBELOW", (0, 0), (-1, -1), 1.4, self.primary),
        ]))
        # Filete doble, como en el membrete del canvas.
        fino = Table([[""]], colWidths=[self.content_width], rowHeights=[1.2 * mm])
        fino.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.5, self.separator)]))
        return [table, fino, Spacer(1, self.block_spacing)]

    # Las mismas piezas formales que en el canvas (`draw_title_block`,
    # `draw_section`, `draw_fields`), para los documentos con Platypus.
    def title_flowables(self, title, subtitle=None, meta=None):
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

        hexa = self._hex
        izq = [Paragraph(f"<b>{_esc(title.upper())}</b>", ParagraphStyle(
            "t", fontName=self.font_bold, fontSize=self.title_size - 2,
            leading=(self.title_size - 2) * 1.2, textColor=self.title_color))]
        if subtitle:
            izq.append(Paragraph(_esc(subtitle), ParagraphStyle(
                "st", fontName=self.font_bold, fontSize=self.size + 0.5,
                leading=self.size * 1.4, textColor=self.primary)))
        meta = [(k, v) for k, v in (meta or []) if v not in (None, "")]
        der = [Paragraph(f'<font color="{hexa(self.secondary)}" size="{self.size - 2}">{_esc(k)}</font>'
                         f'&nbsp;&nbsp;<b>{_esc(v)}</b>', ParagraphStyle(
                             "m", fontName=self.font, fontSize=self.size - 1,
                             leading=self.size + 2, alignment=2, textColor=self.ink))
               for k, v in meta]
        t = Table([[izq, der]], colWidths=[self.content_width * 0.68, self.content_width * 0.32])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LINEBELOW", (0, 0), (-1, -1), 1, self.primary),
        ]))
        return [t, Spacer(1, self.block_spacing)]

    def section_flowable(self, text, number=None):
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import Paragraph, Table, TableStyle

        etiqueta = f"{number}. {text}" if number else text
        p = Paragraph(f"<b>{_esc(etiqueta.upper())}</b>", ParagraphStyle(
            "sec", fontName=self.font_bold, fontSize=self.size - 0.5,
            leading=self.size + 1, textColor=self.primary))
        t = Table([["", p]], colWidths=[1.2 * mm, self.content_width - 1.2 * mm])
        fondo = colors.Color(self.primary.red, self.primary.green, self.primary.blue, alpha=0.08)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), self.primary),
            ("BACKGROUND", (1, 0), (1, 0), fondo),
            ("LEFTPADDING", (1, 0), (1, 0), 2.5 * mm), ("LEFTPADDING", (0, 0), (0, 0), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        t.spaceBefore = 8
        t.spaceAfter = 6
        return t

    def fields_table(self, filas, columnas=3):
        """Cuadrícula etiqueta/valor con bordes, como `draw_fields`."""
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import Paragraph, Table, TableStyle

        est = ParagraphStyle("f", fontName=self.font, fontSize=self.size - 0.5,
                             leading=self.size + 1.5, textColor=self.ink)
        hexa = self._hex
        datos, spans = [], []
        for r, fila in enumerate(filas):
            celdas, col = [], 0
            for celda in fila:
                etiqueta, valor = celda[0], celda[1]
                ocupa = celda[2] if len(celda) > 2 else 1
                texto = "—" if valor in (None, "") else _esc(valor)
                celdas.append(Paragraph(
                    f'<font size="{self.size - 3}" color="{hexa(self.secondary)}">'
                    f'{_esc(str(etiqueta).upper())}</font><br/>{texto}', est))
                celdas += [""] * (ocupa - 1)
                if ocupa > 1:
                    spans.append(("SPAN", (col, r), (col + ocupa - 1, r)))
                col += ocupa
            datos.append(celdas)
        t = Table(datos, colWidths=[self.content_width / columnas] * columnas)
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, self.separator),
            ("BOX", (0, 0), (-1, -1), 0.8, self.separator),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
            *spans,
        ]))
        return t

    @staticmethod
    def _hex(color):
        return "#" + color.hexval()[2:].rjust(6, "0")[-6:]

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
        # El aire entre filas se suma al relleno vertical: es la forma de
        # conseguirlo en reportlab, que no tiene separación de filas.
        vpad = pad * 0.6 + float(t.get("row_spacing_mm", 0)) * mm

        cmds = [
            ("FONTNAME", (0, 0), (-1, header_rows - 1), self.font_bold),
            ("FONTNAME", (0, header_rows), (-1, -1), self.font),
            ("FONTSIZE", (0, 0), (-1, -1), self.size - 1),
            ("TEXTCOLOR", (0, 0), (-1, header_rows - 1), header_text),
            ("TEXTCOLOR", (0, header_rows), (-1, -1), self.ink),
            ("LEFTPADDING", (0, 0), (-1, -1), pad),
            ("RIGHTPADDING", (0, 0), (-1, -1), pad),
            ("TOPPADDING", (0, 0), (-1, -1), vpad),
            ("BOTTOMPADDING", (0, 0), (-1, -1), vpad),
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

    # ── Hojas de cálculo ──────────────────────────────────────────────
    def xlsx_theme(self):
        """
        La misma apariencia, traducida a lo que entiende openpyxl.

        Los reportes en Excel son documentos de la clínica como cualquier
        otro: si la cabecera de las tablas del PDF es del color de la
        marca, la del .xlsx tiene que serlo también. openpyxl quiere los
        colores en 'RRGGBB' sin almohadilla y nombres de fuente reales,
        de ahí la traducción.
        """
        t = self.s["tables"]
        pal = self.s["palette"]
        ty = self.s["typography"]

        def hex6(value, fallback):
            raw = str(value or "").strip() or fallback
            raw = raw.lstrip("#")
            return raw.upper() if len(raw) == 6 else fallback.lstrip("#").upper()

        primary = pal.get("primary") or self.brand.get("primary") or _FALLBACK_PRIMARY
        return {
            "header_bg": hex6(t.get("header_bg") or pal.get("table_header_bg") or primary,
                              _FALLBACK_PRIMARY),
            "header_text": hex6(pal.get("table_header_text"), "#FFFFFF"),
            "body_text": hex6(ty.get("color"), "#1F2937"),
            "zebra": bool(t.get("zebra", True)),
            "zebra_bg": hex6(t.get("zebra_color"), "#F9FAFB"),
            "font": _XLSX_FONTS.get(ty.get("family"), "Calibri"),
            "size": float(ty.get("size_pt", 10)),
        }

    # ── Estilo derivado ───────────────────────────────────────────────
    def for_page(self, size, orientation=None):
        """
        El mismo estilo sobre otra hoja. Lo necesitan los documentos cuyo
        formato de papel forma parte de su naturaleza —la receta se
        imprime en talonario— sin que por ello dejen de seguir la
        identidad configurada por la clínica.
        """
        settings = dict(self.s)
        settings["page"] = dict(self.s["page"])
        settings["page"]["size"] = size
        if orientation:
            settings["page"]["orientation"] = orientation
        return DocumentStyle(settings, brand=self.brand)


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
            # Sin esto, un fallo al leer la configuración hacía que TODOS
            # los documentos salieran con la apariencia por defecto y la
            # clínica no encontrara la causa: sus ajustes «no se aplican».
            logger.warning(
                "No se pudo leer la apariencia de documentos; se usa la de serie",
                exc_info=True,
            )

    if brand is None and tenant is not None:
        brand = _brand_of(tenant)
    return DocumentStyle(settings, brand=brand)


def clinic_snapshot(tenant):
    """
    Datos de la clínica para el encabezado y el pie: nombre, dirección,
    contacto y el logotipo ya abierto como ImageReader.

    Cada vista que emitía un documento repetía este bloque, con el
    resultado de que la historia clínica se quedó sin membrete porque
    allí nadie lo copió. Con un único punto, cualquier documento nuevo lo
    obtiene con una línea.
    """
    if tenant is None:
        return {}
    try:
        from apps.configuration.models import ClinicBranding

        branding = ClinicBranding.objects.filter(tenant=tenant).first()
    except Exception:
        branding = None

    logo_reader = None
    if branding and branding.logo:
        try:
            from reportlab.lib.utils import ImageReader

            logo_reader = ImageReader(branding.logo.path)
        except Exception:
            logo_reader = None      # logotipo ilegible: el documento sale igual

    return {
        "name": (branding.display_name if branding and branding.display_name
                 else getattr(tenant, "name", "")),
        "logo_reader": logo_reader,
        "address": branding.address if branding else "",
        "phone": branding.phone if branding else "",
        "email": branding.email if branding else "",
    }


def _brand_of(tenant):
    """Color de marca de la clínica, para heredarlo cuando la paleta lo deja vacío."""
    try:
        from apps.configuration.models import ClinicBranding

        row = ClinicBranding.objects.filter(tenant=tenant).first()
        if row and isinstance(row.theme, dict):
            return {"primary": row.theme.get("primary") or ""}
    except Exception:
        logger.warning("No se pudo leer la marca de la clínica", exc_info=True)
    return {}
