"""
Exportación de reportes a Excel (RF-REP-06).
Genera el .xlsx en memoria con openpyxl y lo devuelve como descarga.
Son datos ya calculados (no fórmulas), así que no requiere recálculo.

La apariencia sale del motor de estilos (`apps.common.document_style`),
igual que en los PDF: un reporte en Excel es un documento de la clínica
y no tiene por qué llevar otros colores que el resto (Sprint 64).
"""

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill


def build_xlsx(title, headers, rows, style=None):
    """
    Construye un .xlsx en memoria con un encabezado con estilo y las filas.
    Devuelve los bytes listos para una HttpResponse de descarga.

    `style` es el DocumentStyle de la clínica. Sin él se usa el estilo
    por defecto, que reproduce el aspecto anterior al motor.
    """
    from apps.common.document_style import get_document_style

    theme = (style or get_document_style(None)).xlsx_theme()

    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]  # Excel limita el nombre de hoja a 31 chars

    header_font = Font(name=theme["font"], size=theme["size"],
                       bold=True, color=theme["header_text"])
    header_fill = PatternFill("solid", start_color=theme["header_bg"])
    body_font = Font(name=theme["font"], size=theme["size"], color=theme["body_text"])
    zebra_fill = PatternFill("solid", start_color=theme["zebra_bg"])

    ws.append(headers)
    for col, _ in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(vertical="center")

    for i, row in enumerate(rows):
        ws.append(row)
        for col, _ in enumerate(headers, start=1):
            cell = ws.cell(row=i + 2, column=col)
            cell.font = body_font
            if theme["zebra"] and i % 2 == 1:
                cell.fill = zebra_fill

    # La cabecera queda fija al desplazarse: en un reporte largo es la
    # diferencia entre poder leerlo y no.
    ws.freeze_panes = "A2"

    # Ancho de columnas automático (aproximado)
    for col, header in enumerate(headers, start=1):
        max_len = max([len(str(header))] + [len(str(r[col - 1])) for r in rows]) if rows else len(str(header))
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = max_len + 4

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
