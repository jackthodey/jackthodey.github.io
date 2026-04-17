# =============================================================================
# DATA QUALITY ASSESSMENT TOOL – FLASK APPLICATION
# =============================================================================
# Run locally:
#   pip install -r requirements.txt
#   python app.py
# Then open http://localhost:5000
# =============================================================================

from __future__ import annotations

import io
import uuid
import traceback
from typing import Dict

import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file, session

from questions  import QUESTIONS, DIMENSION_LABELS
from standards  import DATA_STANDARDS
from profiler   import profile_dataframe
from scorer     import calculate_governance_score, calculate_combined_score, get_tier, get_recommendations
from report     import generate_pdf_report

app = Flask(__name__)
app.secret_key = "dq-tool-local-secret-change-if-shared"  # only used for server-side session
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB upload cap

# Simple in-process CSV store (single-user local tool)
_csv_store: Dict[str, pd.DataFrame] = {}


# =============================================================================
# Page routes
# =============================================================================

@app.route("/")
def index():
    return render_template("index.html")


# =============================================================================
# API – metadata
# =============================================================================

@app.route("/api/questions", methods=["GET"])
def get_questions():
    """Return the full questionnaire structure."""
    return jsonify({
        "questions":         QUESTIONS,
        "dimension_labels":  DIMENSION_LABELS,
    })


@app.route("/api/standards", methods=["GET"])
def get_standards():
    """Return available data standards grouped by category."""
    grouped: Dict[str, list] = {}
    for sid, meta in DATA_STANDARDS.items():
        cat = meta.get("category", "Other")
        grouped.setdefault(cat, []).append({
            "id":          sid,
            "name":        meta["name"],
            "description": meta["description"],
            "example":     meta.get("example", ""),
        })
    return jsonify(grouped)


# =============================================================================
# API – CSV upload & preview
# =============================================================================

@app.route("/api/upload", methods=["POST"])
def upload_csv():
    """
    Accept a CSV file, store it server-side, and return a preview + column list.
    Returns a session_id that must be echoed back in /api/assess.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files["file"]
    if not f.filename or not f.filename.lower().endswith(".csv"):
        return jsonify({"error": "Please upload a .csv file"}), 400

    try:
        df = pd.read_csv(f)
    except Exception as e:
        return jsonify({"error": f"Could not parse CSV: {e}"}), 400

    if len(df) == 0:
        return jsonify({"error": "The uploaded CSV is empty"}), 400

    sid = str(uuid.uuid4())
    _csv_store[sid] = df

    # Build column type hints for the mapping UI
    col_hints = {}
    for col in df.columns:
        s = df[col].dropna()
        if len(s) == 0:
            col_hints[col] = "empty"
        elif pd.to_numeric(s.head(20), errors="coerce").notna().mean() > 0.8:
            col_hints[col] = "numeric"
        elif pd.to_datetime(s.head(20).astype(str), errors="coerce").notna().mean() > 0.7:
            col_hints[col] = "date"
        else:
            col_hints[col] = "text"

    return jsonify({
        "session_id":  sid,
        "columns":     list(df.columns),
        "col_hints":   col_hints,
        "row_count":   len(df),
        "col_count":   len(df.columns),
        "preview":     df.head(5).fillna("").to_dict(orient="records"),
    })


# =============================================================================
# API – full assessment
# =============================================================================

@app.route("/api/assess", methods=["POST"])
def assess():
    """
    Run the full assessment.

    Expected JSON body:
    {
        "table_name":         string,
        "governance_answers": { "q1": 3, "q2": 2, ... },
        "session_id":         string or null,   // from /api/upload
        "column_standards":   { "col_name": "standard_id", ... }
    }
    """
    data = request.get_json(force=True)

    table_name         = data.get("table_name", "Unnamed Table")
    governance_answers = data.get("governance_answers", {})
    session_id         = data.get("session_id")
    column_standards   = data.get("column_standards", {})

    # Convert string keys to int for answers
    governance_answers = {k: int(v) for k, v in governance_answers.items() if v is not None}

    # Governance scoring
    try:
        gov_result = calculate_governance_score(governance_answers)
    except Exception as e:
        return jsonify({"error": f"Governance scoring failed: {e}"}), 500

    # Profiling (optional)
    prof_result = None
    if session_id and session_id in _csv_store:
        try:
            df = _csv_store[session_id]
            prof_result = profile_dataframe(df, column_standards)
        except Exception as e:
            prof_result = None
            app.logger.warning(f"Profiling failed: {e}\n{traceback.format_exc()}")

    # Combined score & tier
    combined = calculate_combined_score(
        gov_result["overall"],
        prof_result["overall_score"] if prof_result else None,
    )
    tier = get_tier(combined["combined_score"])
    recs = get_recommendations(gov_result, prof_result, tier)

    return jsonify({
        "table_name":      table_name,
        "governance":      gov_result,
        "profiling":       prof_result,
        "combined":        combined,
        "tier":            tier,
        "recommendations": recs,
    })


# =============================================================================
# API – PDF report
# =============================================================================

@app.route("/api/report", methods=["POST"])
def create_report():
    """
    Generate and return a PDF report.
    Accepts the same result payload returned by /api/assess.
    """
    data = request.get_json(force=True)
    try:
        pdf_buf = generate_pdf_report(data)
        table_name = data.get("table_name", "report").replace(" ", "_")
        filename   = f"DQ_Assessment_{table_name}.pdf"
        return send_file(
            pdf_buf,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        return jsonify({"error": f"PDF generation failed: {e}", "detail": traceback.format_exc()}), 500


# =============================================================================
# Housekeeping
# =============================================================================

@app.route("/api/clear/<session_id>", methods=["DELETE"])
def clear_session(session_id: str):
    """Remove a stored CSV from memory."""
    _csv_store.pop(session_id, None)
    return jsonify({"ok": True})


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") != "production"
    print("\n  Data Quality Assessment Tool")
    print("  ─────────────────────────────")
    print(f"  Open http://localhost:{port} in your browser\n")
    app.run(debug=debug, host="0.0.0.0", port=port)
