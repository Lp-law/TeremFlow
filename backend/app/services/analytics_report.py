"""
Client-facing report generation (PDF/DOCX) from Analytics v2 data.
RTL-friendly layout; no case identifiers or internal-only fields.
"""
from __future__ import annotations

import io
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
    from docx.shared import Cm, Pt
    from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False


CASE_TYPE_LABELS: dict[str, str] = {
    "COURT": 'תיק ביהמ"ש',
    "DEMAND_LETTER": "מכתב דרישה",
    "SMALL_CLAIMS": "תביעות קטנות",
}


def _chart_closing_stage_png(distributions: dict) -> bytes | None:
    """Render closing_stage distribution as horizontal bar chart PNG. Returns PNG bytes or None."""
    if not HAS_MATPLOTLIB:
        return None
    closing = distributions.get("closing_stage") or []
    if not closing:
        return None
    labels = [r.get("label") or r.get("code", "") for r in closing]
    counts = [int(r.get("count", 0)) for r in closing]
    if not labels or not counts:
        return None
    fig, ax = plt.subplots(figsize=(5, max(3, len(labels) * 0.4)))
    y_pos = range(len(labels))
    ax.barh(y_pos, counts, color="steelblue", height=0.6)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("תיקים")
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


def build_report_pdf(data: dict, template_id: str, brand: dict | None) -> bytes:
    """Generate PDF report (RTL-friendly, ReportLab). No case identifiers."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    style_rtl = ParagraphStyle(
        name="RTL",
        parent=styles["Normal"],
        alignment=2,  # TA_RIGHT
        fontSize=11,
    )
    style_title = ParagraphStyle(
        name="TitleRTL",
        parent=styles["Heading1"],
        alignment=2,
        fontSize=16,
    )
    story = []

    title = "דו״ח סיכום פעילות"
    if template_id == "T2":
        title = "דו״ח סניפים"
    elif template_id == "T3":
        title = "דו״ח סוגי תיקים"
    story.append(Paragraph(title, style_title))
    story.append(Spacer(1, 0.5 * cm))

    filters = data.get("filters") or {}
    story.append(Paragraph(f"תקופה: {filters.get('start_date', '')} – {filters.get('end_date', '')} | תיקים בפילטר: {filters.get('denominator_cases', 0)}", style_rtl))
    story.append(Spacer(1, 0.5 * cm))

    kpis = data.get("kpis") or {}
    story.append(Paragraph("<b>מפתחות ביצוע</b>", style_rtl))
    story.append(Paragraph(f"שכ״ט ממוצע לפי שלבים: {_fmt_ils(kpis.get('avg_stage_fee_ils'))} ₪", style_rtl))
    story.append(Paragraph(f"שכ״ט ממוצע לפי ריטיינר (תיאורטי): {_fmt_ils(kpis.get('avg_retainer_fee_ils'))} ₪", style_rtl))
    story.append(Paragraph(f"הוצאות ממוצעות לתיק: {_fmt_ils(kpis.get('avg_expenses_ils'))} ₪", style_rtl))
    extra = data.get("extra_metrics") or {}
    if extra.get("closing_stage_index_denominator_cases"):
        story.append(Paragraph(f"שלב סיום ממוצע (תיקי ביהמ״ש): {float(extra.get('avg_closing_stage_index', 0)):.2f} (מבוסס על {extra.get('closing_stage_index_denominator_cases')} תיקים)", style_rtl))
    story.append(Spacer(1, 0.5 * cm))

    for bullet in _narrative_bullets(data):
        story.append(Paragraph(f"• {bullet}", style_rtl))
    story.append(Spacer(1, 0.8 * cm))

    # Closing stage chart
    chart_png = _chart_closing_stage_png(data.get("distributions") or {})
    if chart_png:
        try:
            img = Image(io.BytesIO(chart_png), width=12 * cm, height=8 * cm)
            story.append(Paragraph("<b>התפלגות שלב סיום (תיקים סגורים)</b>", style_rtl))
            story.append(img)
            story.append(Spacer(1, 0.5 * cm))
        except Exception:
            pass

    # Branch × case_type volume table
    dist = data.get("distributions") or {}
    branch_ct = dist.get("branch_case_type") or []
    if branch_ct:
        story.append(Paragraph("<b>נפח לפי סניף וסוג תיק</b>", style_rtl))
        table_data = [["סניף", "סוג תיק", "כמות"]]
        for r in branch_ct[:15]:
            bn = r.get("branch_name") or "ללא סניף"
            ct = CASE_TYPE_LABELS.get(str(r.get("case_type", "")), str(r.get("case_type", "")))
            table_data.append([bn, ct, str(r.get("count", 0))])
        t = Table(table_data, colWidths=[5 * cm, 5 * cm, 2 * cm])
        t.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.5 * cm))

    # Branch fee averages table
    branch_fee = data.get("branch_fee_averages") or []
    if branch_fee:
        story.append(Paragraph("<b>שכ״ט ממוצע לפי סניף</b>", style_rtl))
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
        t.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(t)

    doc.build(story)
    buf.seek(0)
    return buf.read()


def build_report_docx(data: dict, template_id: str, brand: dict | None) -> bytes:
    """Generate DOCX report (RTL paragraphs, tables, chart image). No case identifiers."""
    if not HAS_DOCX:
        raise RuntimeError("python-docx is not installed")
    doc = Document()
    # RTL for body
    title = "דו״ח סיכום פעילות"
    if template_id == "T2":
        title = "דו״ח סניפים"
    elif template_id == "T3":
        title = "דו״ח סוגי תיקים"
    p = doc.add_paragraph(title)
    p.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
    p.runs[0].bold = True
    p.runs[0].font.size = Pt(18)

    filters = data.get("filters") or {}
    p2 = doc.add_paragraph(f"תקופה: {filters.get('start_date', '')} – {filters.get('end_date', '')} | תיקים: {filters.get('denominator_cases', 0)}")
    p2.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT

    doc.add_paragraph()
    doc.add_heading("מפתחות ביצוע", level=1)
    kpis = data.get("kpis") or {}
    for line in [
        f"שכ״ט ממוצע לפי שלבים: {_fmt_ils(kpis.get('avg_stage_fee_ils'))} ₪",
        f"שכ״ט ממוצע לפי ריטיינר: {_fmt_ils(kpis.get('avg_retainer_fee_ils'))} ₪",
        f"הוצאות ממוצעות לתיק: {_fmt_ils(kpis.get('avg_expenses_ils'))} ₪",
    ]:
        pr = doc.add_paragraph(line)
        pr.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT

    doc.add_paragraph()
    doc.add_heading("סיכום", level=1)
    for bullet in _narrative_bullets(data):
        pr = doc.add_paragraph(bullet)
        pr.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT

    chart_png = _chart_closing_stage_png(data.get("distributions") or {})
    if chart_png:
        doc.add_paragraph()
        doc.add_heading("התפלגות שלב סיום", level=1)
        doc.add_picture(io.BytesIO(chart_png), width=Cm(12))

    branch_fee = data.get("branch_fee_averages") or []
    if branch_fee:
        doc.add_paragraph()
        doc.add_heading("שכ״ט ממוצע לפי סניף", level=1)
        table = doc.add_table(rows=1 + len(branch_fee), cols=5)
        table.rows[0].cells[0].text = "סניף"
        table.rows[0].cells[1].text = "תיקים"
        table.rows[0].cells[2].text = "שכ״ט שלבים"
        table.rows[0].cells[3].text = "שכ״ט ריטיינר"
        table.rows[0].cells[4].text = "הוצאות"
        for i, r in enumerate(branch_fee):
            row = table.rows[i + 1]
            row.cells[0].text = str(r.get("branch_name", ""))
            row.cells[1].text = str(r.get("cases_count", 0))
            row.cells[2].text = _fmt_ils(r.get("avg_stage_fee_ils"))
            row.cells[3].text = _fmt_ils(r.get("avg_retainer_fee_ils"))
            row.cells[4].text = _fmt_ils(r.get("avg_expenses_ils"))

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
