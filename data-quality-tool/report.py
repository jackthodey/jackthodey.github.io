# =============================================================================
# DATA QUALITY ASSESSMENT TOOL – PDF REPORT GENERATOR
# =============================================================================
# Uses ReportLab's "Platypus" layout engine to produce a multi-section PDF
# report summarising the full assessment outcome.
#
# ReportLab key concepts used here:
#   SimpleDocTemplate – a document with a single frame (no complex multi-column layout)
#   story             – Python list of "Flowables" (Paragraph, Spacer, Table, etc.)
#                       that ReportLab lays out top-to-bottom automatically
#   ParagraphStyle    – defines font, size, colour, and alignment for a block of text
#   Table / TableStyle – grid layout with per-cell styling (borders, padding, colour)
#   HRFlowable        – a horizontal rule line
#   KeepTogether      – wraps flowables so they don't split across a page break
# =============================================================================

from __future__ import annotations  # Forward-reference type hints for Python 3.9

import io            # io.BytesIO: in-memory bytes buffer — the PDF is written here, not to disk
from datetime import datetime  # Used to embed the current date/time in the report header
from typing import Any, Dict, Optional, List  # Type hints

# ReportLab colour tools
from reportlab.lib import colors                           # Named colours (colors.white, colors.HexColor)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT  # Text alignment constants for ParagraphStyle

from reportlab.lib.pagesizes import A4  # A4 page dimensions in points (595.28 × 841.89 pt)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  # Style infrastructure
from reportlab.lib.units import mm  # Millimetre unit: 1mm = 2.8346 pt — used for readable margin values

# ReportLab Platypus flowable classes (building blocks placed in the story list)
from reportlab.platypus import (
    BaseDocTemplate,   # Advanced multi-frame document (imported but SimpleDocTemplate used instead)
    Frame,             # Named page region (not used directly)
    PageTemplate,      # Page layout template (not used directly)
    Paragraph,         # A block of text with a ParagraphStyle applied
    Spacer,            # Invisible vertical gap between flowables
    Table,             # A grid of cells (used for all tabular data)
    TableStyle,        # Style rules applied to a Table
    HRFlowable,        # Horizontal rule (dividing line)
    KeepTogether,      # Wrapper that prevents its contents splitting across a page break
)
from reportlab.platypus import SimpleDocTemplate  # Single-column document — simpler API than BaseDocTemplate

# ── Colour palette ─────────────────────────────────────────────────────────────
# Define named colours used throughout the report for consistency.
# HexColor() converts a CSS-style hex string to a ReportLab Color object.

GOLD_HEX   = "#C9A84C"                   # Amber gold for Gold tier badge
SILVER_HEX = "#8A8A8A"                   # Mid-grey for Silver tier badge
BRONZE_HEX = "#A0522D"                   # Sienna brown for Bronze tier badge
DARK       = colors.HexColor("#1A1A2E")  # Near-black for headings and body text
MID        = colors.HexColor("#4A4A6A")  # Mid-blue-grey for secondary text and labels
LIGHT_BG   = colors.HexColor("#F7F7FB")  # Very light lavender for table row backgrounds
ACCENT     = colors.HexColor("#4361EE")  # Royal blue for score values and divider lines
RULE       = colors.HexColor("#E0E0E0")  # Light grey for table grid lines and HR lines


def _tier_colour(tier: str) -> colors.Color:
    """
    Return the ReportLab Color for a tier key string.
    Maps "gold" → GOLD_HEX, "silver" → SILVER_HEX, "bronze" → BRONZE_HEX.
    Falls back to BRONZE_HEX for unrecognised tier keys.
    """
    mapping = {"gold": GOLD_HEX, "silver": SILVER_HEX, "bronze": BRONZE_HEX}
    # colors.HexColor() converts the selected hex string to a ReportLab Color object
    return colors.HexColor(mapping.get(tier, BRONZE_HEX))


def generate_pdf_report(data: Dict[str, Any]) -> io.BytesIO:
    """
    Build the full PDF report and return it as an in-memory BytesIO buffer.

    The caller (app.py /api/report) passes the complete assessment result dict
    and streams the returned buffer directly to the browser as a file download.

    Expected keys in *data*:
        table_name      – str: dataset name for the report title
        governance      – dict from scorer.calculate_governance_score()
        profiling       – dict from profiler.profile_dataframe(), or None
        combined        – dict from scorer.calculate_combined_score()
        tier            – dict from scorer.get_tier()
        recommendations – list from scorer.get_recommendations()
    """
    # Create an in-memory bytes buffer — ReportLab writes the PDF bytes here instead of a file
    buf = io.BytesIO()

    # SimpleDocTemplate configures the overall PDF document.
    # pagesize=A4 sets the page dimensions.
    # Margins are set in millimetres using the mm unit (converted to points internally).
    doc = SimpleDocTemplate(
        buf,                                   # Write to the in-memory buffer
        pagesize=A4,                           # A4 paper (595 × 842 points)
        leftMargin=20 * mm,                    # 20 mm left margin
        rightMargin=20 * mm,                   # 20 mm right margin
        topMargin=18 * mm,                     # 18 mm top margin
        bottomMargin=18 * mm,                  # 18 mm bottom margin
        title="Data Quality Assessment Report",  # PDF document metadata title
        author="Data Quality Assessment Tool",   # PDF document metadata author
    )

    # Build the ParagraphStyle dictionary (font, size, colour for each text role)
    styles = _build_styles()

    # The "story" is the ordered list of Flowables that make up the document content.
    # ReportLab's layout engine processes this list top-to-bottom, paginating as needed.
    story  = []

    # ── Extract fields from the result dict ────────────────────────────────────
    table_name    = data.get("table_name", "Unnamed Table")   # Dataset name
    tier_data     = data.get("tier", {})                       # Tier dict (label, colour, etc.)
    combined_data = data.get("combined", {})                   # Combined score dict
    gov_data      = data.get("governance", {})                 # Governance result dict
    prof_data     = data.get("profiling")                      # Profiling result dict (or None)
    recs          = data.get("recommendations", [])            # List of recommendation dicts

    tier_label     = tier_data.get("label", "Bronze")          # Display label e.g. "Gold"
    tier_key       = tier_data.get("tier", "bronze")           # Internal key e.g. "gold"
    tier_col       = _tier_colour(tier_key)                    # ReportLab Color for the tier
    combined_score = combined_data.get("combined_score", 0)    # Numeric 0–100 score

    # ── Section: Header ────────────────────────────────────────────────────────
    # Paragraph() creates a text flowable; the style controls its appearance.
    story.append(Paragraph("DATA QUALITY ASSESSMENT", styles["report_header"]))  # Large bold title
    story.append(Spacer(1, 2 * mm))  # 2mm vertical gap
    # HRFlowable() draws a horizontal dividing line across the full page width
    story.append(HRFlowable(width="100%", thickness=2, color=ACCENT))  # 2pt thick blue rule
    story.append(Spacer(1, 3 * mm))  # 3mm gap after the rule

    # Dataset name in bold within the subtitle style
    story.append(Paragraph(f"Table: <b>{table_name}</b>", styles["subtitle"]))

    # Current date and time formatted as "01 January 2025  14:30"
    story.append(Paragraph(
        f"Assessment Date: {datetime.now().strftime('%d %B %Y  %H:%M')}",
        styles["meta"]   # Smaller, muted style for metadata
    ))
    story.append(Spacer(1, 6 * mm))  # Larger gap before the tier badge

    # ── Section: Tier badge ────────────────────────────────────────────────────
    # A two-cell table: left cell = tier name, right cell = numeric score.
    # Table() accepts a 2D list of cell contents (Paragraphs or strings).
    tier_table = Table(
        [[Paragraph(f"{tier_label.upper()} TIER", styles["tier_badge"]),          # Left cell: "GOLD TIER"
          Paragraph(f"{combined_score:.1f}<font size='10'>/100</font>", styles["score_large"])]],  # Right cell: score
        colWidths=["60%", "40%"],  # Left cell takes 60% of page width; right takes 40%
    )
    tier_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),         # Light background for entire badge row
        ("ROUNDEDCORNERS", [8]),                              # 8pt corner radius (visual softening)
        ("TOPPADDING",    (0, 0), (-1, -1), 8),              # 8pt padding above each cell
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),              # 8pt padding below each cell
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),             # 12pt padding on the left
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),             # 12pt padding on the right
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),                  # Right-align the score cell
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),              # Vertically centre both cells
    ]))
    story.append(tier_table)  # Add the badge table to the story
    story.append(Spacer(1, 3 * mm))

    # Tier description text below the badge
    story.append(Paragraph(tier_data.get("description", ""), styles["body"]))
    story.append(Spacer(1, 6 * mm))

    # ── Section: Score breakdown table ────────────────────────────────────────
    story.append(Paragraph("Score Breakdown", styles["section_heading"]))
    story.append(Spacer(1, 2 * mm))

    # Extract score components from the combined result dict
    gov_score  = combined_data.get("governance_score", 0)
    prof_score = combined_data.get("profiling_score")
    gov_w      = combined_data.get("weights_used", {}).get("governance", 0.6)  # Effective gov weight
    pro_w      = combined_data.get("weights_used", {}).get("profiling", 0.4)   # Effective prof weight

    # Build the table rows.  Header row first, then data rows.
    score_rows = [
        ["Component", "Score", "Weight", "Contribution"],   # Header row
        ["Governance Questionnaire",
         f"{gov_score:.1f}",                                 # Gov score to 1 d.p.
         f"{gov_w*100:.0f}%",                               # Weight as a percentage
         f"{combined_data.get('governance_contribution', 0):.1f}"],  # Weighted contribution points
    ]

    if prof_score is not None:
        # Only add the profiling row if profiling data exists
        score_rows.append([
            "CSV Data Profiling",
            f"{prof_score:.1f}",
            f"{pro_w*100:.0f}%",
            f"{combined_data.get('profiling_contribution', 0):.1f}",
        ])

    # Final row: show the combined total
    score_rows.append(["", "", "COMBINED", f"{combined_score:.1f}"])

    score_table = Table(score_rows, colWidths=["45%", "18%", "18%", "19%"])  # 4 columns, widths sum to 100%
    _apply_table_style(score_table, header_bg=DARK, stripe_bg=LIGHT_BG)     # Dark header, alternating rows
    story.append(score_table)
    story.append(Spacer(1, 6 * mm))

    # ── Section: Governance dimension scores ───────────────────────────────────
    story.append(Paragraph("Governance Dimension Scores", styles["section_heading"]))
    story.append(Spacer(1, 2 * mm))

    # Import DIMENSION_LABELS here to get the ordered label→key mapping
    from questions import DIMENSION_LABELS  # Local import to avoid circular dependency at module level
    dim_scores = gov_data.get("dimension_scores", {})  # Per-dimension 0–100 scores

    dim_rows = [["Dimension", "Score", "Maturity Level"]]  # Header row
    for dim_id, label in DIMENSION_LABELS.items():         # Iterate in defined display order
        score    = dim_scores.get(dim_id, 0)               # Score for this dimension (default 0 if missing)
        maturity = _maturity_label(score)                  # Convert score to "Ad hoc" / "Informal" / etc.
        dim_rows.append([label, f"{score:.1f}", maturity])

    dim_table = Table(dim_rows, colWidths=["55%", "20%", "25%"])
    _apply_table_style(dim_table, header_bg=DARK, stripe_bg=LIGHT_BG)
    story.append(dim_table)
    story.append(Spacer(1, 6 * mm))

    # ── Section: Profiling dimension scores (only if a CSV was uploaded) ───────
    if prof_data:
        story.append(Paragraph("Data Profiling Results", styles["section_heading"]))
        story.append(Spacer(1, 2 * mm))

        # Dataset summary statistics
        rc  = prof_data.get("row_count", 0)                  # Total rows
        cc  = prof_data.get("col_count", 0)                  # Total columns
        dup = prof_data.get("duplicate_rows", 0)             # Duplicate row count
        gx  = "Yes" if prof_data.get("gx_used") else "No"   # Whether GX was used

        # 2×4 summary grid (label, value, label, value pattern)
        summary_rows = [
            ["Rows analysed", str(rc), "Columns analysed", str(cc)],
            ["Duplicate rows", str(dup), "GX validation used", gx],
        ]
        st = Table(summary_rows, colWidths=["30%", "20%", "30%", "20%"])
        st.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),        # Light background for all cells
            ("FONTNAME",  (0, 0), (-1, -1), "Helvetica"),       # Regular font for values
            ("FONTNAME",  (0, 0), (0, -1), "Helvetica-Bold"),   # Bold for left-side labels (column 0)
            ("FONTNAME",  (2, 0), (2, -1), "Helvetica-Bold"),   # Bold for right-side labels (column 2)
            ("FONTSIZE",  (0, 0), (-1, -1), 9),                 # 9pt text throughout
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, RULE),             # 0.5pt grey grid lines
        ]))
        story.append(st)
        story.append(Spacer(1, 3 * mm))

        # Profiling dimension scores table
        prof_dims = prof_data.get("dimensions", {})            # Dict of dimension_key → detail dict
        prof_rows = [["Quality Dimension", "Score", "Detail"]] # Header row

        # Iterate in a fixed display order (rather than dict insertion order)
        for dim_key in ["completeness", "uniqueness", "validity", "consistency", "timeliness"]:
            if dim_key not in prof_dims:
                continue  # Skip dimensions not present in the result (e.g. if profiling was partial)
            d      = prof_dims[dim_key]
            dscore = d.get("score", 0)       # Numeric score 0–100
            desc   = d.get("description", "") # Human-readable description from the profiler
            prof_rows.append([dim_key.title(), f"{dscore:.1f}", desc])  # .title() = "Completeness"

        pt = Table(prof_rows, colWidths=["22%", "15%", "63%"])  # Description column gets most space
        _apply_table_style(pt, header_bg=DARK, stripe_bg=LIGHT_BG)
        story.append(pt)
        story.append(Spacer(1, 6 * mm))

    # ── Section: Recommendations ───────────────────────────────────────────────
    if recs:
        story.append(Paragraph("Priority Improvement Actions", styles["section_heading"]))
        story.append(Spacer(1, 2 * mm))

        for i, rec in enumerate(recs, 1):  # Enumerate from 1 for display numbering
            priority = rec.get("priority", "medium")

            # Colour the priority badge: red for high, amber for medium
            pri_col  = colors.HexColor("#DC2626") if priority == "high" else colors.HexColor("#D97706")
            area     = rec.get("area", "")        # Area name e.g. "Governance & Ownership"
            action   = rec.get("action", "")      # The improvement action text
            src_score = rec.get("score", 0)       # The current score driving this recommendation

            # Each recommendation is a 2×2 table:
            #   Row 0: area + score (left) | priority badge (right)
            #   Row 1: action text spanning both columns
            rec_table = Table(
                [[Paragraph(f"<b>{i}. {area}</b> — Score: {src_score:.0f}/100", styles["body"]),
                  Paragraph(priority.upper(), styles["priority_tag"])],
                 [Paragraph(action, styles["small"]), ""]],  # Empty string in right cell of row 1
                colWidths=["80%", "20%"],
                rowHeights=[None, None],  # Auto height for both rows
            )
            rec_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BG),         # Light background for header row
                ("BACKGROUND", (0, 1), (-1, 1), colors.white),      # White background for action row
                ("TOPPADDING",    (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING",   (0, 0), (-1, -1), 10),
                ("SPAN", (0, 1), (1, 1)),                           # Merge both cells in row 1 (action text spans full width)
                ("GRID", (0, 0), (-1, -1), 0.5, RULE),             # Grid lines around all cells
            ]))
            # KeepTogether prevents this recommendation card splitting across a page break
            story.append(KeepTogether(rec_table))
            story.append(Spacer(1, 2 * mm))

    # ── Section: Footer ────────────────────────────────────────────────────────
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=RULE))  # Thin grey rule above footer
    story.append(Spacer(1, 2 * mm))

    thresholds = tier_data.get("thresholds", {"gold": 80, "silver": 60})

    # Tier thresholds and weight split line
    story.append(Paragraph(
        f"Tier thresholds — Gold: ≥{thresholds['gold']} · Silver: ≥{thresholds['silver']} · Bronze: &lt;{thresholds['silver']}  "
        f"| Scoring: {int((combined_data.get('weights_used', {}).get('governance', 0.6))*100)}% governance / "
        f"{int((combined_data.get('weights_used', {}).get('profiling', 0.4))*100)}% profiling",
        styles["footer"],
    ))

    # Methodology attribution line
    story.append(Paragraph(
        "Assessment methodology based on DAMA-DMBOK2, DCAM (EDM Council), ISO 8000, and ISO/IEC 27001.",
        styles["footer"],
    ))

    # ── Build (render) the PDF ─────────────────────────────────────────────────
    # doc.build() iterates the story list, lays out each flowable, and writes
    # the binary PDF to the BytesIO buffer.
    doc.build(story)

    # Seek back to the start of the buffer so the caller can read from byte 0
    buf.seek(0)

    return buf  # Return the populated BytesIO buffer ready for streaming


# =============================================================================
# Style helpers
# =============================================================================

def _build_styles() -> Dict[str, ParagraphStyle]:
    """
    Create and return a dict of named ParagraphStyle objects.

    ParagraphStyle arguments:
        fontName  – must be a ReportLab built-in or registered font name
        fontSize  – in points
        textColor – a ReportLab Color object
        leading   – line height in points (vertical space between baselines)
        spaceAfter – extra vertical space added after the paragraph (points)
        alignment – TA_LEFT, TA_CENTER, or TA_RIGHT
    """
    base = getSampleStyleSheet()  # Load ReportLab's built-in default styles (not used directly)
    s = {}  # Our custom styles dict

    # Large bold title at the top of the report
    s["report_header"] = ParagraphStyle(
        "report_header",
        fontName="Helvetica-Bold",  # Helvetica-Bold is always available in ReportLab
        fontSize=20,                # Large title size
        textColor=DARK,             # Near-black text
        spaceAfter=0,               # No extra space (we manually add a Spacer)
        leading=24,                 # 24pt line height (larger than font to avoid clipping)
    )

    # Dataset name line below the report title
    s["subtitle"] = ParagraphStyle(
        "subtitle",
        fontName="Helvetica-Bold",
        fontSize=12,
        textColor=MID,   # Mid-grey — slightly de-emphasised relative to the title
        spaceAfter=2,
    )

    # Small metadata text (date, author, etc.)
    s["meta"] = ParagraphStyle(
        "meta",
        fontName="Helvetica",
        fontSize=9,
        textColor=MID,
        spaceAfter=0,
    )

    # Large tier name inside the badge table
    s["tier_badge"] = ParagraphStyle(
        "tier_badge",
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=DARK,
        alignment=TA_LEFT,  # Left-align within its table cell
    )

    # Oversized score number on the right side of the badge table
    s["score_large"] = ParagraphStyle(
        "score_large",
        fontName="Helvetica-Bold",
        fontSize=22,      # Larger than tier label to make the score the focal point
        textColor=ACCENT, # Accent blue draws attention to the score
        alignment=TA_RIGHT,
    )

    # Bold section headings (e.g. "Score Breakdown", "Governance Dimension Scores")
    s["section_heading"] = ParagraphStyle(
        "section_heading",
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=DARK,
        borderPad=0,
        spaceAfter=0,
    )

    # Standard body text used in descriptions and recommendation header rows
    s["body"] = ParagraphStyle(
        "body",
        fontName="Helvetica",
        fontSize=9,
        textColor=DARK,
        leading=13,  # 13pt leading for readable body text
    )

    # Smaller text used in recommendation action rows
    s["small"] = ParagraphStyle(
        "small",
        fontName="Helvetica",
        fontSize=8,
        textColor=MID,   # Muted colour for secondary text
        leading=12,
    )

    # Priority badge (HIGH / MEDIUM) in the top-right of a recommendation card
    s["priority_tag"] = ParagraphStyle(
        "priority_tag",
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=colors.white,  # White text on the coloured background set by TableStyle
        alignment=TA_CENTER,
    )

    # Tiny footer text at the bottom of the report
    s["footer"] = ParagraphStyle(
        "footer",
        fontName="Helvetica",
        fontSize=7.5,
        textColor=MID,
        alignment=TA_CENTER,  # Centred footer text
        leading=11,
    )

    return s


def _apply_table_style(
    tbl: Table,
    header_bg: colors.Color = DARK,       # Background colour for the first (header) row
    stripe_bg: colors.Color = LIGHT_BG,   # Background colour for alternating data rows
) -> None:
    """
    Apply a consistent style to a data table: dark header row, alternating
    row colours, grid lines, and appropriate padding.

    TableStyle tuples have the form:
        (command_name, from_cell, to_cell, *args)
    where from_cell and to_cell are (col_index, row_index) tuples.
    (0, 0) = top-left cell;  (-1, -1) = bottom-right cell (relative).
    """
    tbl.setStyle(TableStyle([
        # ── Header row (row 0) ─────────────────────────────────────────────────
        ("BACKGROUND",    (0, 0), (-1, 0), header_bg),    # Dark background for header
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white), # White text on dark background
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),  # Bold header text
        ("FONTSIZE",      (0, 0), (-1, 0), 9),            # 9pt header font
        ("TOPPADDING",    (0, 0), (-1, 0), 6),            # 6pt top padding for header
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),            # 6pt bottom padding for header
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),           # 8pt left padding for ALL rows
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),           # 8pt right padding for ALL rows
        # ── Data rows (row 1 onward) ───────────────────────────────────────────
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"), # Regular font for data
        ("FONTSIZE",      (0, 1), (-1, -1), 9),           # 9pt data font
        ("TOPPADDING",    (0, 1), (-1, -1), 4),           # Slightly less padding than header
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        # ROWBACKGROUNDS alternates background colours for data rows (zebra striping)
        # [colors.white, stripe_bg] = row 1 white, row 2 stripe, row 3 white, row 4 stripe, ...
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, stripe_bg]),
        ("GRID",          (0, 0), (-1, -1), 0.5, RULE),  # 0.5pt grey grid lines for all cells
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),    # Vertically centre all cell content
    ]))


def _maturity_label(score: float) -> str:
    """
    Convert a 0–100 governance dimension score into a DAMA maturity level label.

    Bands:
        75–100 → "Optimised"  (4 = actively enforced and continuously improved)
        50–74  → "Defined"    (3 = formal, documented practice)
        25–49  → "Informal"   (2 = undocumented, inconsistent)
        0–24   → "Ad hoc"     (1 = no practice exists)
    """
    if score >= 75:
        return "Optimised"  # Top band — formal, enforced, continuously improved
    if score >= 50:
        return "Defined"    # Second band — formal but not yet optimised
    if score >= 25:
        return "Informal"   # Third band — exists but undocumented
    return "Ad hoc"         # Bottom band — no practice exists
