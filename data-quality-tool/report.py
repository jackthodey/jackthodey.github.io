# =============================================================================
# DATA QUALITY ASSESSMENT TOOL – PDF REPORT GENERATOR
# =============================================================================
# Uses ReportLab to produce a clean, professional single-page PDF report
# summarising the assessment outcome.
# =============================================================================

from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Dict, Optional, List

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table,
    TableStyle, HRFlowable, KeepTogether,
)
from reportlab.platypus import SimpleDocTemplate

# ── Palette ───────────────────────────────────────────────────────────────────
GOLD_HEX   = "#C9A84C"
SILVER_HEX = "#8A8A8A"
BRONZE_HEX = "#A0522D"
DARK       = colors.HexColor("#1A1A2E")
MID        = colors.HexColor("#4A4A6A")
LIGHT_BG   = colors.HexColor("#F7F7FB")
ACCENT     = colors.HexColor("#4361EE")
RULE       = colors.HexColor("#E0E0E0")


def _tier_colour(tier: str) -> colors.Color:
    mapping = {"gold": GOLD_HEX, "silver": SILVER_HEX, "bronze": BRONZE_HEX}
    return colors.HexColor(mapping.get(tier, BRONZE_HEX))


def generate_pdf_report(data: Dict[str, Any]) -> io.BytesIO:
    """
    Build the PDF report and return it as a BytesIO buffer.

    Expected keys in *data*:
        table_name  – str
        governance  – dict from scorer.calculate_governance_score()
        profiling   – dict from profiler.profile_dataframe() or None
        combined    – dict from scorer.calculate_combined_score()
        tier        – dict from scorer.get_tier()
        recommendations – list from scorer.get_recommendations()
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Data Quality Assessment Report",
        author="Data Quality Assessment Tool",
    )

    styles = _build_styles()
    story  = []

    table_name    = data.get("table_name", "Unnamed Table")
    tier_data     = data.get("tier", {})
    combined_data = data.get("combined", {})
    gov_data      = data.get("governance", {})
    prof_data     = data.get("profiling")
    recs          = data.get("recommendations", [])

    tier_label    = tier_data.get("label", "Bronze")
    tier_key      = tier_data.get("tier", "bronze")
    tier_col      = _tier_colour(tier_key)
    combined_score = combined_data.get("combined_score", 0)

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph("DATA QUALITY ASSESSMENT", styles["report_header"]))
    story.append(Spacer(1, 2 * mm))
    story.append(HRFlowable(width="100%", thickness=2, color=ACCENT))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph(f"Table: <b>{table_name}</b>", styles["subtitle"]))
    story.append(Paragraph(
        f"Assessment Date: {datetime.now().strftime('%d %B %Y  %H:%M')}",
        styles["meta"]
    ))
    story.append(Spacer(1, 6 * mm))

    # ── Tier badge ────────────────────────────────────────────────────────────
    tier_table = Table(
        [[Paragraph(f"{tier_label.upper()} TIER", styles["tier_badge"]),
          Paragraph(f"{combined_score:.1f}<font size='10'>/100</font>", styles["score_large"])]],
        colWidths=["60%", "40%"],
    )
    tier_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
        ("ROUNDEDCORNERS", [8]),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(tier_table)
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(tier_data.get("description", ""), styles["body"]))
    story.append(Spacer(1, 6 * mm))

    # ── Score breakdown ───────────────────────────────────────────────────────
    story.append(Paragraph("Score Breakdown", styles["section_heading"]))
    story.append(Spacer(1, 2 * mm))

    gov_score  = combined_data.get("governance_score", 0)
    prof_score = combined_data.get("profiling_score")
    gov_w      = combined_data.get("weights_used", {}).get("governance", 0.6)
    pro_w      = combined_data.get("weights_used", {}).get("profiling", 0.4)

    score_rows = [
        ["Component", "Score", "Weight", "Contribution"],
        ["Governance Questionnaire",
         f"{gov_score:.1f}",
         f"{gov_w*100:.0f}%",
         f"{combined_data.get('governance_contribution', 0):.1f}"],
    ]
    if prof_score is not None:
        score_rows.append([
            "CSV Data Profiling",
            f"{prof_score:.1f}",
            f"{pro_w*100:.0f}%",
            f"{combined_data.get('profiling_contribution', 0):.1f}",
        ])
    score_rows.append(["", "", "COMBINED", f"{combined_score:.1f}"])

    score_table = Table(score_rows, colWidths=["45%", "18%", "18%", "19%"])
    _apply_table_style(score_table, header_bg=DARK, stripe_bg=LIGHT_BG)
    story.append(score_table)
    story.append(Spacer(1, 6 * mm))

    # ── Governance dimension scores ───────────────────────────────────────────
    story.append(Paragraph("Governance Dimension Scores", styles["section_heading"]))
    story.append(Spacer(1, 2 * mm))

    from questions import DIMENSION_LABELS
    dim_scores = gov_data.get("dimension_scores", {})
    dim_rows = [["Dimension", "Score", "Maturity Level"]]
    for dim_id, label in DIMENSION_LABELS.items():
        score = dim_scores.get(dim_id, 0)
        maturity = _maturity_label(score)
        dim_rows.append([label, f"{score:.1f}", maturity])

    dim_table = Table(dim_rows, colWidths=["55%", "20%", "25%"])
    _apply_table_style(dim_table, header_bg=DARK, stripe_bg=LIGHT_BG)
    story.append(dim_table)
    story.append(Spacer(1, 6 * mm))

    # ── Profiling dimension scores ────────────────────────────────────────────
    if prof_data:
        story.append(Paragraph("Data Profiling Results", styles["section_heading"]))
        story.append(Spacer(1, 2 * mm))

        # Summary stats
        rc = prof_data.get("row_count", 0)
        cc = prof_data.get("col_count", 0)
        dup = prof_data.get("duplicate_rows", 0)
        gx  = "Yes" if prof_data.get("gx_used") else "No"

        summary_rows = [
            ["Rows analysed", str(rc), "Columns analysed", str(cc)],
            ["Duplicate rows", str(dup), "GX validation used", gx],
        ]
        st = Table(summary_rows, colWidths=["30%", "20%", "30%", "20%"])
        st.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
            ("FONTNAME",  (0, 0), (-1, -1), "Helvetica"),
            ("FONTNAME",  (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME",  (2, 0), (2, -1), "Helvetica-Bold"),
            ("FONTSIZE",  (0, 0), (-1, -1), 9),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, RULE),
        ]))
        story.append(st)
        story.append(Spacer(1, 3 * mm))

        # Dimension scores
        prof_dims = prof_data.get("dimensions", {})
        prof_rows = [["Quality Dimension", "Score", "Detail"]]
        for dim_key in ["completeness", "uniqueness", "validity", "consistency", "timeliness"]:
            if dim_key not in prof_dims:
                continue
            d     = prof_dims[dim_key]
            dscore = d.get("score", 0)
            desc   = d.get("description", "")
            prof_rows.append([dim_key.title(), f"{dscore:.1f}", desc])

        pt = Table(prof_rows, colWidths=["22%", "15%", "63%"])
        _apply_table_style(pt, header_bg=DARK, stripe_bg=LIGHT_BG)
        story.append(pt)
        story.append(Spacer(1, 6 * mm))

    # ── Recommendations ───────────────────────────────────────────────────────
    if recs:
        story.append(Paragraph("Priority Improvement Actions", styles["section_heading"]))
        story.append(Spacer(1, 2 * mm))

        for i, rec in enumerate(recs, 1):
            priority = rec.get("priority", "medium")
            pri_col  = colors.HexColor("#DC2626") if priority == "high" else colors.HexColor("#D97706")
            area     = rec.get("area", "")
            action   = rec.get("action", "")
            src_score = rec.get("score", 0)

            rec_table = Table(
                [[Paragraph(f"<b>{i}. {area}</b> — Score: {src_score:.0f}/100", styles["body"]),
                  Paragraph(priority.upper(), styles["priority_tag"])],
                 [Paragraph(action, styles["small"]), ""]],
                colWidths=["80%", "20%"],
                rowHeights=[None, None],
            )
            rec_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BG),
                ("BACKGROUND", (0, 1), (-1, 1), colors.white),
                ("TOPPADDING",    (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING",   (0, 0), (-1, -1), 10),
                ("SPAN", (0, 1), (1, 1)),
                ("GRID", (0, 0), (-1, -1), 0.5, RULE),
            ]))
            story.append(KeepTogether(rec_table))
            story.append(Spacer(1, 2 * mm))

    # ── Tier scale footnote ───────────────────────────────────────────────────
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=RULE))
    story.append(Spacer(1, 2 * mm))
    thresholds = tier_data.get("thresholds", {"gold": 80, "silver": 60})
    story.append(Paragraph(
        f"Tier thresholds — Gold: ≥{thresholds['gold']} · Silver: ≥{thresholds['silver']} · Bronze: &lt;{thresholds['silver']}  "
        f"| Scoring: {int((combined_data.get('weights_used', {}).get('governance', 0.6))*100)}% governance / "
        f"{int((combined_data.get('weights_used', {}).get('profiling', 0.4))*100)}% profiling",
        styles["footer"],
    ))
    story.append(Paragraph(
        "Assessment methodology based on DAMA-DMBOK2, DCAM (EDM Council), ISO 8000, and ISO/IEC 27001.",
        styles["footer"],
    ))

    doc.build(story)
    buf.seek(0)
    return buf


# =============================================================================
# Style helpers
# =============================================================================

def _build_styles() -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    s = {}

    s["report_header"] = ParagraphStyle(
        "report_header",
        fontName="Helvetica-Bold",
        fontSize=20,
        textColor=DARK,
        spaceAfter=0,
        leading=24,
    )
    s["subtitle"] = ParagraphStyle(
        "subtitle",
        fontName="Helvetica-Bold",
        fontSize=12,
        textColor=MID,
        spaceAfter=2,
    )
    s["meta"] = ParagraphStyle(
        "meta",
        fontName="Helvetica",
        fontSize=9,
        textColor=MID,
        spaceAfter=0,
    )
    s["tier_badge"] = ParagraphStyle(
        "tier_badge",
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=DARK,
        alignment=TA_LEFT,
    )
    s["score_large"] = ParagraphStyle(
        "score_large",
        fontName="Helvetica-Bold",
        fontSize=22,
        textColor=ACCENT,
        alignment=TA_RIGHT,
    )
    s["section_heading"] = ParagraphStyle(
        "section_heading",
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=DARK,
        borderPad=0,
        spaceAfter=0,
    )
    s["body"] = ParagraphStyle(
        "body",
        fontName="Helvetica",
        fontSize=9,
        textColor=DARK,
        leading=13,
    )
    s["small"] = ParagraphStyle(
        "small",
        fontName="Helvetica",
        fontSize=8,
        textColor=MID,
        leading=12,
    )
    s["priority_tag"] = ParagraphStyle(
        "priority_tag",
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=colors.white,
        alignment=TA_CENTER,
    )
    s["footer"] = ParagraphStyle(
        "footer",
        fontName="Helvetica",
        fontSize=7.5,
        textColor=MID,
        alignment=TA_CENTER,
        leading=11,
    )
    return s


def _apply_table_style(
    tbl: Table,
    header_bg: colors.Color = DARK,
    stripe_bg: colors.Color = LIGHT_BG,
) -> None:
    tbl.setStyle(TableStyle([
        # Header row
        ("BACKGROUND",    (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 9),
        ("TOPPADDING",    (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        # Data rows
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 1), (-1, -1), 9),
        ("TOPPADDING",    (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, stripe_bg]),
        ("GRID",          (0, 0), (-1, -1), 0.5, RULE),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))


def _maturity_label(score: float) -> str:
    if score >= 75:
        return "Optimised"
    if score >= 50:
        return "Defined"
    if score >= 25:
        return "Informal"
    return "Ad hoc"
