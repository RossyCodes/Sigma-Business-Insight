"""
pdf_report.py — In-memory PDF report generation (reportlab).

Builds a clean, print-friendly PDF snapshot of the current dashboard state:
header (title / file / date range / timestamp / filter note), KPI summary,
Sales Trend line chart, Top Products table, Category table, and an optional
Insights section.  Everything is generated in memory (BytesIO) — nothing is
written to disk on the server.

Design choice: charts are drawn with reportlab's native vector graphics
(instead of Plotly->kaleido PNGs) so the PDF works on machines where kaleido's
headless-Chrome backend is unavailable, and stays crisp when printed.
"""

import re
from datetime import datetime
from io import BytesIO
from typing import Optional

import pandas as pd
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from translations import t

# ---------------------------------------------------------------------------
# Sigma palette — light / print-friendly
# ---------------------------------------------------------------------------

BLUE = colors.HexColor("#2F6FED")
BLUE_DARK = colors.HexColor("#1B3A6B")
INK = colors.HexColor("#0B1830")
MUTED = colors.HexColor("#5A6B85")
FAINT = colors.HexColor("#93A3BB")
LINE = colors.HexColor("#D8E2F0")
PAPER = colors.HexColor("#FFFFFF")
TILE = colors.HexColor("#F4F8FE")
ICE = colors.HexColor("#8FD4FF")

PAGE_W, PAGE_H = A4
MARGIN = 16 * mm
# Printable width (A4 minus left/right margins) — every Drawing must fit inside it
PRINT_W = PAGE_W - 2 * MARGIN

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

_TITLE = ParagraphStyle(
    "SigmaTitle",
    fontName="Helvetica-Bold",
    fontSize=19,
    leading=23,
    textColor=INK,
    spaceAfter=2,
)
_SUBTITLE = ParagraphStyle(
    "SigmaSub",
    fontName="Helvetica",
    fontSize=9,
    leading=13,
    textColor=MUTED,
)
_H2 = ParagraphStyle(
    "SigmaH2",
    fontName="Helvetica-Bold",
    fontSize=12,
    leading=15,
    textColor=BLUE_DARK,
    spaceBefore=14,
    spaceAfter=6,
)
_BODY = ParagraphStyle(
    "SigmaBody",
    fontName="Helvetica",
    fontSize=9,
    leading=13,
    textColor=INK,
)
_MUTED = ParagraphStyle(
    "SigmaMuted",
    fontName="Helvetica-Oblique",
    fontSize=9,
    leading=13,
    textColor=MUTED,
)
_NOTE = ParagraphStyle(
    "SigmaNote",
    fontName="Helvetica-Oblique",
    fontSize=8,
    leading=11,
    textColor=MUTED,
)
_KPI_LABEL = ParagraphStyle(
    "KpiLabel",
    fontName="Helvetica",
    fontSize=7,
    leading=9,
    textColor=MUTED,
    alignment=TA_CENTER,
)
_KPI_VALUE = ParagraphStyle(
    "KpiValue",
    fontName="Helvetica-Bold",
    fontSize=12,
    leading=15,
    textColor=BLUE,
    alignment=TA_CENTER,
)
_CELL = ParagraphStyle(
    "Cell",
    fontName="Helvetica",
    fontSize=8.5,
    leading=11,
    textColor=INK,
)
_CELL_MONO = ParagraphStyle(
    "CellMono",
    fontName="Courier",
    fontSize=8.5,
    leading=11,
    textColor=INK,
)


def _esc(text: str) -> str:
    """Escape a string for reportlab's mini-HTML Paragraph markup.

    Drops characters reportlab's built-in WinAnsi fonts cannot encode
    (e.g. emoji from AI/quick-insights text) so PDF generation never crashes
    on non-Latin-1 content and no "?" placeholders appear in the report.
    """
    text = str(text)
    # Keep only WinAnsi-encodable chars — drop emoji/arrows entirely
    text = text.encode("cp1252", errors="ignore").decode("cp1252")
    # Collapse whitespace left behind by dropped emoji
    text = re.sub(r"\s+", " ", text).strip()
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _md_to_plain(text: str) -> str:
    """Minimal markdown -> plain text for the insights section."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)      # bold
    text = re.sub(r"\*(.+?)\*", r"\1", text)            # italic
    text = re.sub(r"^#{1,4}\s*", "", text, flags=re.M)  # headings
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)  # links [t](url) -> t
    text = re.sub(r"^[\s]*[-*]\s+", "•  ", text, flags=re.M)  # bullets

    # Convert simple markdown tables (| a | b |) into readable plain lines
    out_lines = []
    for line in text.split("\n"):
        s = line.strip()
        # Drop separator rows like |---|---|
        if re.match(r"^\|?[\s:|-]+\|?$", s) and "-" in s:
            continue
        if s.startswith("|") or s.endswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            cells = [c for c in cells if c]
            if cells:
                out_lines.append("  ·  ".join(cells))
                continue
        out_lines.append(line)
    text = "\n".join(out_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Chart builders (reportlab native vector drawing)
# ---------------------------------------------------------------------------


def _trend_chart(df: pd.DataFrame, date_col: str, amount_col: str) -> Optional[Drawing]:
    """Sales line chart aggregated by day/week/month (vector). Returns a Drawing or None.

    Aggregation granularity is picked from the date range span: daily (<=60 days),
    weekly (>60 days), or monthly (>365 days).
    """
    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        return None

    span_days = (df[date_col].max() - df[date_col].min()).days
    if span_days > 365:
        # pandas >= 2.2 renamed the monthly alias 'M' -> 'ME'
        freq = "ME" if tuple(int(x) for x in pd.__version__.split(".")[:2]) >= (2, 2) else "M"
    elif span_days > 60:
        freq = "W"
    else:
        freq = "D"

    trend = (
        df.groupby(pd.Grouper(key=date_col, freq=freq))[amount_col]
        .sum()
        .dropna()
        .sort_index()
    )
    if trend.empty:
        return None

    xs = list(range(len(trend)))
    ys = [float(v) for v in trend.values]
    max_y = max(ys) if ys else 0.0

    chart = LinePlot()
    chart.x = 45
    chart.y = 40
    # Keep the plot area inside the printable width, with room to the right so
    # the last x-axis date label is not clipped at the page edge.
    chart.width = PRINT_W - chart.x - 18
    chart.height = 150
    chart.data = [list(zip(xs, ys))]
    chart.lines[0].strokeColor = BLUE
    chart.lines[0].strokeWidth = 2
    chart.lines[0].symbol = None

    chart.xValueAxis.valueMin = 0
    chart.xValueAxis.valueMax = max(xs) if xs else 1
    chart.xValueAxis.gridStrokeColor = LINE
    chart.xValueAxis.strokeColor = LINE
    chart.xValueAxis.labels.fontSize = 6.5
    chart.xValueAxis.labels.angle = 0
    chart.xValueAxis.labelTextFormat = (
        lambda v: trend.index[int(v)].strftime("%b %Y" if freq in ("M", "ME") else "%d %b")
        if 0 <= int(v) < len(trend.index)
        else ""
    )

    chart.yValueAxis.valueMin = 0
    chart.yValueAxis.valueMax = max(max_y * 1.15, 1.0)
    chart.yValueAxis.gridStrokeColor = LINE
    chart.yValueAxis.strokeColor = LINE
    chart.yValueAxis.labels.fontSize = 6.5
    chart.yValueAxis.labelTextFormat = lambda v: f"RM {v:,.0f}"

    d = Drawing(PRINT_W, 200)
    d.add(chart)
    return d


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------


def build_report_pdf(
    df: pd.DataFrame,
    detected: dict,
    filename: str,
    lang: str = "en",
    filter_desc: str = "",
    insights_text: str = "",
) -> bytes:
    """Build the report PDF in memory and return the bytes."""
    date_col = detected.get("date_col")
    amount_col = detected.get("amount_col")
    product_col = detected.get("product_col")
    category_col = detected.get("category_col")

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
        title=f"Sigma — {t('pdf_title', lang)}",
        author="Sigma",
    )

    story = []

    # ---- Header ----
    story.append(Paragraph(_esc(t("pdf_title", lang)), _TITLE))
    story.append(Spacer(1, 3))

    # date range
    date_range = "—"
    if date_col and date_col in df.columns and pd.api.types.is_datetime64_any_dtype(df[date_col]):
        dmin = df[date_col].min()
        dmax = df[date_col].max()
        if pd.notna(dmin) and pd.notna(dmax):
            date_range = f"{dmin.strftime('%d %b %Y')} – {dmax.strftime('%d %b %Y')}"

    # Show the analyzed file name as readable words (no underscores)
    display_name = filename.replace("_", " ")
    header_lines = [
        f"<b>{_esc(t('pdf_file', lang))}:</b> {_esc(display_name)}",
        f"<b>{_esc(t('pdf_date_range', lang))}:</b> {_esc(date_range)}",
        f"<b>{_esc(t('pdf_generated', lang))}:</b> {datetime.now().strftime('%d %b %Y, %H:%M')}",
    ]
    story.append(Paragraph("<br/>".join(header_lines), _SUBTITLE))

    # Filter scope note
    if filter_desc:
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            f"<b>{_esc(t('pdf_scope_note', lang))}</b> {_esc(filter_desc)}",
            _NOTE,
        ))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1, color=LINE))
    story.append(Spacer(1, 4))

    # ---- KPI summary ----
    total_sales = df[amount_col].sum() if amount_col and amount_col in df.columns else 0
    tx_count = len(df)
    avg_order = (
        df[amount_col].mean()
        if amount_col and amount_col in df.columns and len(df) > 0
        else 0
    )

    best_day = "—"
    if date_col and amount_col and date_col in df.columns and amount_col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[date_col]):
            daily_sales = df.groupby(df[date_col].dt.day_name())[amount_col].sum()
            if not daily_sales.empty:
                best_day = daily_sales.idxmax()

    story.append(Paragraph(_esc(t("pdf_section_kpis", lang)), _H2))
    kpi_rows = [
        [t("total_sales", lang), t("transactions_kpi", lang),
         t("avg_order_value", lang), t("best_day", lang)],
        [f"RM {total_sales:,.2f}", f"{tx_count:,}",
         f"RM {avg_order:,.2f}", str(best_day)],
    ]
    kpi_cells = [
        [Paragraph(_esc(c), _KPI_LABEL) for c in kpi_rows[0]],
        [Paragraph(_esc(c), _KPI_VALUE) for c in kpi_rows[1]],
    ]
    kpi_table = Table(kpi_cells, colWidths=[(PAGE_W - 2 * MARGIN) / 4.0] * 4)
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TILE),
        ("BACKGROUND", (0, 1), (-1, 1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.75, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 6))

    # ---- Sales trend ----
    trend_ok = bool(
        date_col and amount_col
        and date_col in df.columns and amount_col in df.columns
        and pd.api.types.is_datetime64_any_dtype(df[date_col])
    )
    if trend_ok:
        story.append(Paragraph(_esc(t("pdf_section_trend", lang)), _H2))
        chart = _trend_chart(df, date_col, amount_col)
        if chart is not None:
            story.append(chart)
        else:
            story.append(Paragraph(_esc(t("trend_no_parse", lang)), _MUTED))
    else:
        story.append(Paragraph(_esc(t("pdf_section_trend", lang)), _H2))
        story.append(Paragraph(_esc(t("trend_no_data", lang)), _MUTED))

    # ---- Top products ----
    story.append(Paragraph(_esc(t("pdf_section_products", lang)), _H2))
    if product_col and amount_col and product_col in df.columns and amount_col in df.columns:
        prod_sales = df.groupby(product_col, as_index=False)[amount_col].sum()
        prod_sales = prod_sales.sort_values(amount_col, ascending=False).head(10)
        if prod_sales.empty:
            story.append(Paragraph(_esc(t("products_no_data", lang)), _MUTED))
        else:
            total = float(df[amount_col].sum()) or 1.0
            header = [Paragraph(_esc(h), _CELL) for h in
                      [t("pdf_col_product", lang), t("pdf_col_sales", lang), t("pdf_col_share", lang)]]
            rows = [header]
            for _, r in prod_sales.iterrows():
                share = (float(r[amount_col]) / total) * 100
                rows.append([
                    Paragraph(_esc(r[product_col]), _CELL),
                    Paragraph(f"RM {float(r[amount_col]):,.2f}", _CELL_MONO),
                    Paragraph(f"{share:.1f}%", _CELL_MONO),
                ])
            prod_table = Table(rows, colWidths=[(PAGE_W - 2 * MARGIN) * 0.52,
                                                (PAGE_W - 2 * MARGIN) * 0.24,
                                                (PAGE_W - 2 * MARGIN) * 0.24])
            prod_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), TILE),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TILE]),
            ]))
            story.append(prod_table)
    else:
        story.append(Paragraph(_esc(t("products_no_col", lang)), _MUTED))

    # ---- Category breakdown ----
    if category_col and amount_col and category_col in df.columns and amount_col in df.columns:
        cat_sales = df.groupby(category_col, as_index=False)[amount_col].sum()
        cat_sales = cat_sales.sort_values(amount_col, ascending=False)
        if not cat_sales.empty and len(cat_sales) >= 2:
            story.append(Paragraph(_esc(t("pdf_section_category", lang)), _H2))
            total = float(df[amount_col].sum()) or 1.0
            header = [Paragraph(_esc(h), _CELL) for h in
                      [t("pdf_col_category", lang), t("pdf_col_sales", lang), t("pdf_col_share", lang)]]
            rows = [header]
            for _, r in cat_sales.head(8).iterrows():
                share = (float(r[amount_col]) / total) * 100
                rows.append([
                    Paragraph(_esc(r[category_col]), _CELL),
                    Paragraph(f"RM {float(r[amount_col]):,.2f}", _CELL_MONO),
                    Paragraph(f"{share:.1f}%", _CELL_MONO),
                ])
            cat_table = Table(rows, colWidths=[(PAGE_W - 2 * MARGIN) * 0.52,
                                               (PAGE_W - 2 * MARGIN) * 0.24,
                                               (PAGE_W - 2 * MARGIN) * 0.24])
            cat_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), TILE),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TILE]),
            ]))
            story.append(cat_table)

    # ---- Insights & Recommendations ----
    if insights_text and insights_text.strip():
        story.append(Paragraph(_esc(t("pdf_section_insights", lang)), _H2))
        plain = _md_to_plain(insights_text)
        for para in plain.split("\n\n"):
            para = para.strip()
            if para:
                story.append(Paragraph(_esc(para), _BODY))
                story.append(Spacer(1, 4))

    # ---- Footer ----
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.75, color=LINE))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"{_esc(t('pdf_footer_generated', lang))} · {_esc(t('pdf_footer_snapshot', lang))}",
        _NOTE,
    ))

    def _on_page(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(FAINT)
        canvas.drawCentredString(PAGE_W / 2, 9 * mm, f"{t('pdf_footer_generated', lang)} — sigma.app")
        canvas.drawRightString(PAGE_W - MARGIN, 9 * mm, str(_doc.page))
        canvas.restoreState()

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()
