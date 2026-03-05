"""
Client-facing report generation (PDF/DOCX) from Analytics v2 data.
RTL-friendly layout; no case identifiers or internal-only fields.
Logo and colors from brand; no external URL fetch (SSRF-safe).
"""
from __future__ import annotations

import base64
import io
import re
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, Image

# Optional matplotlib for chart (bar chart as PNG)
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

# Optional python-docx for DOCX
try:
    from docx import Document
    from docx.shared import Cm, Pt, RGBColor
    from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False


CASE_TYPE_LABELS: dict[str, str] = {
    "COURT": 'תיק ביהמ"ש',
    "DEMAND_LETTER": "מכתב דרישה",
    "SMALL_CLAIMS": "תביעות קטנות",
}

DEFAULT_PRIMARY = "#1F4E79"
DEFAULT_ACCENT = "#2E75B6"
DEFAULT_HEADER_TEXT = "#FFFFFF"


def _parse_hex(hex_str: str | None) -> tuple[float, float, float]:
    """Parse #RRGGBB to (r,g,b) in 0..1. Returns (0.12, 0.31, 0.47) for default primary if invalid."""
    if not hex_str or not isinstance(hex_str, str):
        hex_str = DEFAULT_PRIMARY
    hex_str = hex_str.strip()
    m = re.match(r"#?([0-9A-Fa-f]{6})$", hex_str)
    if not m:
        return (0.12, 0.31, 0.47)
    s = m.group(1)
    return (int(s[0:2], 16) / 255.0, int(s[2:4], 16) / 255.0, int(s[4:6], 16) / 255.0)


def _hex_to_reportlab(hex_str: str | None):
    """ReportLab color from hex."""
    r, g, b = _parse_hex(hex_str)
    return colors.Color(r, g, b)


def _logo_image_from_brand(brand: dict | None, max_width_cm: float = 4.0, max_height_cm: float = 1.5):
    """
    Decode logo from brand['logo_base64'] (data URL or raw base64). No URL fetch.
    Returns ReportLab Image flowable or None.
    """
    if not brand:
        return None
    raw = brand.get("logo_base64")
    if not raw or not isinstance(raw, str):
        return None
    raw = raw.strip()
    # optional data URL prefix
    if raw.startswith("data:"):
        m = re.search(r"base64\s*,\s*(\S+)", raw)
        if m:
            raw = m.group(1)
        else:
            return None
    try:
        img_bytes = base64.b64decode(raw, validate=True)
    except Exception:
        return None
    if not img_bytes:
        return None
    try:
        img = Image(io.BytesIO(img_bytes), width=max_width_cm * cm, height=max_height_cm * cm)
        return img
    except Exception:
        return None


def _chart_closing_stage_png(distributions: dict, primary_hex: str | None = None) -> bytes | None:
    """Render closing_stage as horizontal bar chart. primary_hex for bars; neutral gray for axis. Clean, no heavy grid."""
    if not HAS_MATPLOTLIB:
        return None
    closing = distributions.get("closing_stage") or []
    if not closing:
        return None
    labels = [r.get("label") or r.get("code", "") for r in closing]
    counts = [int(r.get("count", 0)) for r in closing]
    if not labels or not counts:
        return None
    r, g, b = _parse_hex(primary_hex or DEFAULT_PRIMARY)
    bar_color = (r, g, b)
    axis_color = (0.45, 0.45, 0.45)
    fig, ax = plt.subplots(figsize=(5, max(3, len(labels) * 0.4)))
    y_pos = range(len(labels))
    ax.barh(y_pos, counts, color=bar_color, height=0.6)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=9, color=axis_color)
    ax.invert_yaxis()
    ax.set_xlabel("תיקים", fontsize=9, color=axis_color)
    ax.tick_params(axis="x", colors=axis_color)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.set_ticks_position("left")
    ax.xaxis.set_ticks_position("bottom")
    ax.grid(axis="x", alpha=0.25, linestyle="-")
    fig.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close()
    buf.seek(0)
    return buf.read()


def _narrative_bullets(data: dict) -> list[str]:
    """Generate short factual narrative bullets from v2 data (no case IDs)."""
    bullets: list[str] = []
    filters = data.get("filters") or {}
    kpis = data.get("kpis") or {}
    extra = data.get("extra_metrics") or {}
    totals = data.get("totals") or {}
    denom = int(filters.get("denominator_cases") or 0)
    start = filters.get("start_date") or ""
    end = filters.get("end_date") or ""

    if denom > 0:
        bullets.append(f"במהלך התקופה נכללו {denom} תיקים (תאריך פתיחה {start} עד {end}).")
    avg_stage = kpis.get("avg_stage_fee_ils")
    if avg_stage is not None:
        s = str(avg_stage) if not isinstance(avg_stage, (int, float)) else f"{float(avg_stage):,.2f}"
        bullets.append(f"שכ״ט ממוצע לפי שלבים היה {s} ₪.")
    avg_ret = kpis.get("avg_retainer_fee_ils")
    if avg_ret is not None:
        s = str(avg_ret) if not isinstance(avg_ret, (int, float)) else f"{float(avg_ret):,.2f}"
        bullets.append(f"שכ״ט ממוצע לפי ריטיינר (תיאורטי) היה {s} ₪.")
    idx_denom = int(extra.get("closing_stage_index_denominator_cases") or 0)
    if idx_denom > 0:
        avg_idx = float(extra.get("avg_closing_stage_index") or 0)
        bullets.append(f"השלב השכיח לסיום (תיקי ביהמ״ש סגורים): ממוצע שלב {avg_idx:.2f} (מבוסס על {idx_denom} תיקים בשלבים 1–5).")
    by_branch = totals.get("by_branch") or []
    if by_branch:
        top = max(by_branch, key=lambda r: int(r.get("count") or 0))
        bn = top.get("branch_name") or "ללא סניף"
        cnt = top.get("count") or 0
        bullets.append(f"הסניף עם נפח הגבוה ביותר: {bn} ({cnt} תיקים).")
    return bullets


def _fmt_ils(val: Any) -> str:
    if val is None:
        return "0.00"
    if isinstance(val, (int, float)):
        return f"{float(val):,.2f}"
    return str(val)


def _pdf_table_style_with_brand(header_bg, header_text, ncols: int):
    """TableStyle for header row with brand colors and thin separator."""
    return TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (-1, 0), header_text),
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("LINEBELOW", (0, 0), (-1, 0), 1, header_bg),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ])


def build_report_pdf(data: dict, template_id: str, brand: dict | None) -> bytes:
    """Generate PDF report (RTL-friendly, ReportLab). Logo top-right if provided; brand colors on headers/tables."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    primary = _hex_to_reportlab(brand.get("primary_hex") if brand else None)
    accent = _hex_to_reportlab(brand.get("accent_hex") if brand else None)
    header_bg = _hex_to_reportlab((brand or {}).get("header_bg_hex") or (brand or {}).get("primary_hex") or DEFAULT_PRIMARY)
    header_text = _hex_to_reportlab((brand or {}).get("header_text_hex") or DEFAULT_HEADER_TEXT)

    styles = getSampleStyleSheet()
    style_rtl = ParagraphStyle(
        name="RTL",
        parent=styles["Normal"],
        alignment=2,
        fontSize=11,
    )
    style_title = ParagraphStyle(
        name="TitleRTL",
        parent=styles["Heading1"],
        alignment=2,
        fontSize=16,
        textColor=primary,
    )
    style_heading = ParagraphStyle(
        name="HeadingRTL",
        parent=styles["Normal"],
        alignment=2,
        fontSize=12,
        textColor=primary,
        spaceAfter=6,
    )
    story = []

    title = "דו״ח סיכום פעילות"
    if template_id == "T2":
        title = "דו״ח סניפים"
    elif template_id == "T3":
        title = "דו״ח סוגי תיקים"

    logo_img = _logo_image_from_brand(brand)
    filters = data.get("filters") or {}
    period_text = f"תקופה: {filters.get('start_date', '')} – {filters.get('end_date', '')} | תיקים בפילטר: {filters.get('denominator_cases', 0)}"
    if logo_img:
        header_tbl = Table([[Paragraph(title, style_title), logo_img]], colWidths=[12 * cm, 4 * cm])
        header_tbl.setStyle(TableStyle([("ALIGN", (0, 0), (0, 0), "RIGHT"), ("ALIGN", (1, 0), (1, 0), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(header_tbl)
    else:
        story.append(Paragraph(title, style_title))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(period_text, style_rtl))
    story.append(Spacer(1, 0.5 * cm))

    kpis = data.get("kpis") or {}
    story.append(Paragraph("<b>מפתחות ביצוע</b>", style_heading))
    story.append(Paragraph(f"שכ״ט ממוצע לפי שלבים: {_fmt_ils(kpis.get('avg_stage_fee_ils'))} ₪", style_rtl))
    story.append(Paragraph(f"שכ״ט ממוצע לפי ריטיינר (תיאורטי): {_fmt_ils(kpis.get('avg_retainer_fee_ils'))} ₪", style_rtl))
    story.append(Paragraph(f"הוצאות ממוצעות לתיק: {_fmt_ils(kpis.get('avg_expenses_ils'))} ₪", style_rtl))
    extra = data.get("extra_metrics") or {}
    if extra.get("closing_stage_index_denominator_cases"):
        story.append(Paragraph(f"שלב סיום ממוצע (תיקי ביהמ״ש): {float(extra.get('avg_closing_stage_index', 0)):.2f} (מבוסס על {extra.get('closing_stage_index_denominator_cases')} תיקים)", style_rtl))
    story.append(Spacer(1, 0.5 * cm))

    primary_hex = (brand or {}).get("primary_hex") or DEFAULT_PRIMARY
    dist = data.get("distributions") or {}
    branch_ct = dist.get("branch_case_type") or []
    branch_fee = data.get("branch_fee_averages") or []
    case_type_fee = data.get("case_type_fee_averages") or []
    closing_stage = dist.get("closing_stage") or []

    if template_id == "T1":
        for bullet in _narrative_bullets(data):
            story.append(Paragraph(f"• {bullet}", style_rtl))
        story.append(Spacer(1, 0.8 * cm))
        chart_png = _chart_closing_stage_png(dist, primary_hex)
        if chart_png:
            try:
                img = Image(io.BytesIO(chart_png), width=12 * cm, height=8 * cm)
                story.append(Paragraph("<b>התפלגות שלב סיום (תיקים סגורים)</b>", style_heading))
                story.append(img)
                story.append(Spacer(1, 0.5 * cm))
            except Exception:
                pass
        if branch_ct:
            story.append(Paragraph("<b>נפח לפי סניף וסוג תיק</b>", style_heading))
            table_data = [["סניף", "סוג תיק", "כמות"]]
            for r in branch_ct[:15]:
                bn = r.get("branch_name") or "ללא סניף"
                ct = CASE_TYPE_LABELS.get(str(r.get("case_type", "")), str(r.get("case_type", "")))
                table_data.append([bn, ct, str(r.get("count", 0))])
            t = Table(table_data, colWidths=[5 * cm, 5 * cm, 2 * cm])
            t.setStyle(_pdf_table_style_with_brand(header_bg, header_text, 3))
            story.append(t)
            story.append(Spacer(1, 0.5 * cm))
        if branch_fee:
            story.append(Paragraph("<b>שכ״ט ממוצע לפי סניף</b>", style_heading))
            table_data = [["סניף", "תיקים", "שכ״ט שלבים", "שכ״ט ריטיינר", "הוצאות"]]
            for r in branch_fee[:10]:
                table_data.append([
                    str(r.get("branch_name", "")),
                    str(r.get("cases_count", 0)),
                    _fmt_ils(r.get("avg_stage_fee_ils")),
                    _fmt_ils(r.get("avg_retainer_fee_ils")),
                    _fmt_ils(r.get("avg_expenses_ils")),
                ])
            t = Table(table_data, colWidths=[4 * cm, 2 * cm, 3 * cm, 3 * cm, 3 * cm])
            t.setStyle(_pdf_table_style_with_brand(header_bg, header_text, 5))
            story.append(t)

    elif template_id == "T2":
        # T2: branch-focused — big branch fee table first, then volume, then mini insights, then small chart
        if branch_fee:
            story.append(Paragraph("<b>שכ״ט ממוצע לפי סניף</b>", style_heading))
            table_data = [["סניף", "תיקים", "שכ״ט שלבים", "שכ״ט ריטיינר", "הוצאות"]]
            for r in branch_fee:
                table_data.append([
                    str(r.get("branch_name", "")),
                    str(r.get("cases_count", 0)),
                    _fmt_ils(r.get("avg_stage_fee_ils")),
                    _fmt_ils(r.get("avg_retainer_fee_ils")),
                    _fmt_ils(r.get("avg_expenses_ils")),
                ])
            t = Table(table_data, colWidths=[4 * cm, 2 * cm, 3 * cm, 3 * cm, 3 * cm])
            t.setStyle(_pdf_table_style_with_brand(header_bg, header_text, 5))
            story.append(t)
            story.append(Spacer(1, 0.5 * cm))
        if branch_ct:
            story.append(Paragraph("<b>נפח תיקים לפי סניף וסוג תיק</b>", style_heading))
            table_data = [["סניף", "סוג תיק", "כמות"]]
            for r in branch_ct[:20]:
                bn = r.get("branch_name") or "ללא סניף"
                ct = CASE_TYPE_LABELS.get(str(r.get("case_type", "")), str(r.get("case_type", "")))
                table_data.append([bn, ct, str(r.get("count", 0))])
            t = Table(table_data, colWidths=[5 * cm, 5 * cm, 2 * cm])
            t.setStyle(_pdf_table_style_with_brand(header_bg, header_text, 3))
            story.append(t)
            story.append(Spacer(1, 0.5 * cm))
        totals = data.get("totals") or {}
        by_branch = totals.get("by_branch") or []
        if by_branch:
            top_vol = max(by_branch, key=lambda r: int(r.get("count") or 0))
            bn_vol = top_vol.get("branch_name") or "ללא סניף"
            story.append(Paragraph(f"<b>תובנה:</b> הסניף עם נפח הגבוה ביותר: {bn_vol} ({top_vol.get('count', 0)} תיקים).", style_rtl))
        if branch_fee:
            top_fee = max(branch_fee, key=lambda r: float(r.get("avg_stage_fee_ils") or 0))
            story.append(Paragraph(f"<b>תובנה:</b> הסניף עם שכ״ט ממוצע לפי שלבים הגבוה ביותר: {top_fee.get('branch_name', '')} ({_fmt_ils(top_fee.get('avg_stage_fee_ils'))} ₪).", style_rtl))
        story.append(Spacer(1, 0.5 * cm))
        chart_png = _chart_closing_stage_png(dist, primary_hex)
        if chart_png:
            try:
                img = Image(io.BytesIO(chart_png), width=10 * cm, height=6 * cm)
                story.append(Paragraph("<b>התפלגות שלב סיום (תיקים סגורים)</b>", style_heading))
                story.append(img)
            except Exception:
                pass

    else:
        # T3: case-type focused — case_type summary table; closing chart only if CLOSED data present
        if case_type_fee:
            story.append(Paragraph("<b>סיכום לפי סוג תיק</b>", style_heading))
            table_data = [["סוג תיק", "תיקים", "שכ״ט שלבים", "שכ״ט ריטיינר", "הוצאות"]]
            for r in case_type_fee:
                ct_label = CASE_TYPE_LABELS.get(str(r.get("case_type", "")), str(r.get("case_type", "")))
                table_data.append([
                    ct_label,
                    str(r.get("cases_count", 0)),
                    _fmt_ils(r.get("avg_stage_fee_ils")),
                    _fmt_ils(r.get("avg_retainer_fee_ils")),
                    _fmt_ils(r.get("avg_expenses_ils")),
                ])
            t = Table(table_data, colWidths=[4 * cm, 2 * cm, 3 * cm, 3 * cm, 3 * cm])
            t.setStyle(_pdf_table_style_with_brand(header_bg, header_text, 5))
            story.append(t)
            story.append(Spacer(1, 0.5 * cm))
        for bullet in _narrative_bullets(data):
            story.append(Paragraph(f"• {bullet}", style_rtl))
        story.append(Spacer(1, 0.5 * cm))
        if closing_stage:
            chart_png = _chart_closing_stage_png(dist, primary_hex)
            if chart_png:
                try:
                    img = Image(io.BytesIO(chart_png), width=12 * cm, height=8 * cm)
                    story.append(Paragraph("<b>התפלגות שלב סיום (תיקים סגורים)</b>", style_heading))
                    story.append(img)
                except Exception:
                    pass

    doc.build(story)
    buf.seek(0)
    return buf.read()


def _docx_set_cell_shading(cell, hex_str: str) -> None:
    """Set table cell background to hex color (python-docx)."""
    if not HAS_DOCX:
        return
    r, g, b = _parse_hex(hex_str)
    # hex for OOXML is RRGGBB
    hex_val = f"{int(r*255):02X}{int(g*255):02X}{int(b*255):02X}"
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), hex_val)
    tcPr.append(shd)


def _docx_heading_paragraph(doc, text: str, primary_hex: str):
    """Add a heading-style paragraph with primary color (bold, size, color)."""
    from docx.oxml.ns import qn as _qn
    from docx.oxml import OxmlElement as _OxmlElement
    p = doc.add_paragraph()
    p.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(14)
    r, g, b = _parse_hex(primary_hex)
    # set run color via dml
    rPr = run._r.get_or_add_rPr()
    color = _OxmlElement("w:color")
    color.set(_qn("w:val"), f"{int(r*255):02X}{int(g*255):02X}{int(b*255):02X}")
    rPr.append(color)
    return p


def build_report_docx(data: dict, template_id: str, brand: dict | None) -> bytes:
    """Generate DOCX report (RTL, logo at top, brand colors on headings and table headers). No case identifiers."""
    if not HAS_DOCX:
        raise RuntimeError("python-docx is not installed")
    doc = Document()
    primary_hex = (brand or {}).get("primary_hex") or DEFAULT_PRIMARY
    header_bg_hex = (brand or {}).get("header_bg_hex") or (brand or {}).get("primary_hex") or DEFAULT_PRIMARY

    # Logo at top if provided
    raw = (brand or {}).get("logo_base64")
    if raw and isinstance(raw, str):
        raw = raw.strip()
        if raw.startswith("data:"):
            m = re.search(r"base64\s*,\s*(\S+)", raw)
            if m:
                raw = m.group(1)
        if raw:
            try:
                img_bytes = base64.b64decode(raw, validate=True)
                if img_bytes:
                    doc.add_picture(io.BytesIO(img_bytes), width=Cm(3.5))
                    doc.add_paragraph()
            except Exception:
                pass

    title = "דו״ח סיכום פעילות"
    if template_id == "T2":
        title = "דו״ח סניפים"
    elif template_id == "T3":
        title = "דו״ח סוגי תיקים"
    p = doc.add_paragraph(title)
    p.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
    p.runs[0].bold = True
    p.runs[0].font.size = Pt(18)
    r, g, b = _parse_hex(primary_hex)
    p.runs[0].font.color.rgb = RGBColor(int(r * 255), int(g * 255), int(b * 255))

    filters = data.get("filters") or {}
    p2 = doc.add_paragraph(f"תקופה: {filters.get('start_date', '')} – {filters.get('end_date', '')} | תיקים: {filters.get('denominator_cases', 0)}")
    p2.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT

    doc.add_paragraph()
    _docx_heading_paragraph(doc, "מפתחות ביצוע", primary_hex)
    kpis = data.get("kpis") or {}
    for line in [
        f"שכ״ט ממוצע לפי שלבים: {_fmt_ils(kpis.get('avg_stage_fee_ils'))} ₪",
        f"שכ״ט ממוצע לפי ריטיינר: {_fmt_ils(kpis.get('avg_retainer_fee_ils'))} ₪",
        f"הוצאות ממוצעות לתיק: {_fmt_ils(kpis.get('avg_expenses_ils'))} ₪",
    ]:
        pr = doc.add_paragraph(line)
        pr.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT

    dist = data.get("distributions") or {}
    branch_fee = data.get("branch_fee_averages") or []
    branch_ct = dist.get("branch_case_type") or []
    case_type_fee = data.get("case_type_fee_averages") or []
    closing_stage = dist.get("closing_stage") or []

    if template_id == "T1":
        doc.add_paragraph()
        _docx_heading_paragraph(doc, "סיכום", primary_hex)
        for bullet in _narrative_bullets(data):
            pr = doc.add_paragraph(bullet)
            pr.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
        chart_png = _chart_closing_stage_png(dist, primary_hex)
        if chart_png:
            doc.add_paragraph()
            _docx_heading_paragraph(doc, "התפלגות שלב סיום", primary_hex)
            doc.add_picture(io.BytesIO(chart_png), width=Cm(12))
        if branch_ct:
            doc.add_paragraph()
            _docx_heading_paragraph(doc, "נפח לפי סניף וסוג תיק", primary_hex)
            table = doc.add_table(rows=1 + len(branch_ct[:15]), cols=3)
            hdr = table.rows[0].cells
            hdr[0].text, hdr[1].text, hdr[2].text = "סניף", "סוג תיק", "כמות"
            for j in range(3):
                _docx_set_cell_shading(table.rows[0].cells[j], header_bg_hex)
            for i, r in enumerate(branch_ct[:15]):
                row = table.rows[i + 1]
                row.cells[0].text = r.get("branch_name") or "ללא סניף"
                row.cells[1].text = CASE_TYPE_LABELS.get(str(r.get("case_type", "")), str(r.get("case_type", "")))
                row.cells[2].text = str(r.get("count", 0))
        if branch_fee:
            doc.add_paragraph()
            _docx_heading_paragraph(doc, "שכ״ט ממוצע לפי סניף", primary_hex)
            table = doc.add_table(rows=1 + len(branch_fee[:10]), cols=5)
            table.rows[0].cells[0].text = "סניף"
            table.rows[0].cells[1].text = "תיקים"
            table.rows[0].cells[2].text = "שכ״ט שלבים"
            table.rows[0].cells[3].text = "שכ״ט ריטיינר"
            table.rows[0].cells[4].text = "הוצאות"
            for j in range(5):
                _docx_set_cell_shading(table.rows[0].cells[j], header_bg_hex)
            for i, r in enumerate(branch_fee[:10]):
                row = table.rows[i + 1]
                row.cells[0].text = str(r.get("branch_name", ""))
                row.cells[1].text = str(r.get("cases_count", 0))
                row.cells[2].text = _fmt_ils(r.get("avg_stage_fee_ils"))
                row.cells[3].text = _fmt_ils(r.get("avg_retainer_fee_ils"))
                row.cells[4].text = _fmt_ils(r.get("avg_expenses_ils"))

    elif template_id == "T2":
        if branch_fee:
            doc.add_paragraph()
            _docx_heading_paragraph(doc, "שכ״ט ממוצע לפי סניף", primary_hex)
            table = doc.add_table(rows=1 + len(branch_fee), cols=5)
            table.rows[0].cells[0].text = "סניף"
            table.rows[0].cells[1].text = "תיקים"
            table.rows[0].cells[2].text = "שכ״ט שלבים"
            table.rows[0].cells[3].text = "שכ״ט ריטיינר"
            table.rows[0].cells[4].text = "הוצאות"
            for j in range(5):
                _docx_set_cell_shading(table.rows[0].cells[j], header_bg_hex)
            for i, r in enumerate(branch_fee):
                row = table.rows[i + 1]
                row.cells[0].text = str(r.get("branch_name", ""))
                row.cells[1].text = str(r.get("cases_count", 0))
                row.cells[2].text = _fmt_ils(r.get("avg_stage_fee_ils"))
                row.cells[3].text = _fmt_ils(r.get("avg_retainer_fee_ils"))
                row.cells[4].text = _fmt_ils(r.get("avg_expenses_ils"))
        if branch_ct:
            doc.add_paragraph()
            _docx_heading_paragraph(doc, "נפח תיקים לפי סניף וסוג תיק", primary_hex)
            table = doc.add_table(rows=1 + min(20, len(branch_ct)), cols=3)
            table.rows[0].cells[0].text, table.rows[0].cells[1].text, table.rows[0].cells[2].text = "סניף", "סוג תיק", "כמות"
            for j in range(3):
                _docx_set_cell_shading(table.rows[0].cells[j], header_bg_hex)
            for i, r in enumerate(branch_ct[:20]):
                row = table.rows[i + 1]
                row.cells[0].text = r.get("branch_name") or "ללא סניף"
                row.cells[1].text = CASE_TYPE_LABELS.get(str(r.get("case_type", "")), str(r.get("case_type", "")))
                row.cells[2].text = str(r.get("count", 0))
        totals = data.get("totals") or {}
        by_branch = totals.get("by_branch") or []
        if by_branch and branch_fee:
            doc.add_paragraph()
            top_vol = max(by_branch, key=lambda r: int(r.get("count") or 0))
            top_fee = max(branch_fee, key=lambda r: float(r.get("avg_stage_fee_ils") or 0))
            pr = doc.add_paragraph(f"תובנה: סניף נפח גבוה — {top_vol.get('branch_name') or 'ללא סניף'} ({top_vol.get('count', 0)} תיקים). סניף שכ״ט ממוצע גבוה — {top_fee.get('branch_name', '')} ({_fmt_ils(top_fee.get('avg_stage_fee_ils'))} ₪).")
            pr.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
        chart_png = _chart_closing_stage_png(dist, primary_hex)
        if chart_png:
            doc.add_paragraph()
            _docx_heading_paragraph(doc, "התפלגות שלב סיום", primary_hex)
            doc.add_picture(io.BytesIO(chart_png), width=Cm(10))

    else:
        # T3
        if case_type_fee:
            doc.add_paragraph()
            _docx_heading_paragraph(doc, "סיכום לפי סוג תיק", primary_hex)
            table = doc.add_table(rows=1 + len(case_type_fee), cols=5)
            table.rows[0].cells[0].text = "סוג תיק"
            table.rows[0].cells[1].text = "תיקים"
            table.rows[0].cells[2].text = "שכ״ט שלבים"
            table.rows[0].cells[3].text = "שכ״ט ריטיינר"
            table.rows[0].cells[4].text = "הוצאות"
            for j in range(5):
                _docx_set_cell_shading(table.rows[0].cells[j], header_bg_hex)
            for i, r in enumerate(case_type_fee):
                row = table.rows[i + 1]
                row.cells[0].text = CASE_TYPE_LABELS.get(str(r.get("case_type", "")), str(r.get("case_type", "")))
                row.cells[1].text = str(r.get("cases_count", 0))
                row.cells[2].text = _fmt_ils(r.get("avg_stage_fee_ils"))
                row.cells[3].text = _fmt_ils(r.get("avg_retainer_fee_ils"))
                row.cells[4].text = _fmt_ils(r.get("avg_expenses_ils"))
        _docx_heading_paragraph(doc, "סיכום", primary_hex)
        for bullet in _narrative_bullets(data):
            pr = doc.add_paragraph(bullet)
            pr.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
        if closing_stage:
            chart_png = _chart_closing_stage_png(dist, primary_hex)
            if chart_png:
                doc.add_paragraph()
                _docx_heading_paragraph(doc, "התפלגות שלב סיום", primary_hex)
                doc.add_picture(io.BytesIO(chart_png), width=Cm(12))

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()


def build_client_report(
    data: dict,
    template_id: str,
    report_format: str,
    brand: dict | None,
) -> tuple[bytes, str]:
    """
    Build report bytes and suggested filename.
    data: Analytics v2 response as dict (from model_dump(mode="json")).
    Returns (content_bytes, filename).
    """
    date_str = datetime.now().strftime("%Y%m%d")
    if report_format.lower() == "docx":
        content = build_report_docx(data, template_id, brand)
        ext = "docx"
    else:
        content = build_report_pdf(data, template_id, brand)
        ext = "pdf"
    filename = f"client_report_{template_id}_{date_str}.{ext}"
    return (content, filename)
