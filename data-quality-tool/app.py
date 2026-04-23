# =============================================================================
# DATA QUALITY ASSESSMENT TOOL – FLASK APPLICATION
# =============================================================================
from __future__ import annotations

import io
import os
import traceback
from typing import Dict

import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file

from questions import QUESTIONS, DIMENSION_LABELS
from standards import DATA_STANDARDS
from profiler  import profile_dataframe
from scorer    import calculate_governance_score, calculate_combined_score, get_tier, get_recommendations
from report    import generate_pdf_report

app = Flask(__name__)
app.secret_key = "dq-tool-local-secret-change-if-shared"
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64 MB


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/questions", methods=["GET"])
def get_questions():
    return jsonify({"questions": QUESTIONS, "dimension_labels": DIMENSION_LABELS})


@app.route("/api/standards", methods=["GET"])
def get_standards():
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


@app.route("/api/upload", methods=["POST"])
def upload_csv():
    try:
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

        col_hints = {}
        for col in df.columns:
            s = df[col].dropna()
            if len(s) == 0:
                col_hints[col] = "empty"
            elif pd.to_numeric(s.head(20), errors="coerce").notna().mean() > 0.8:
                col_hints[col] = "numeric"
            else:
                try:
                    parsed = pd.to_datetime(s.head(20).astype(str), errors="coerce")
                    col_hints[col] = "date" if parsed.notna().mean() > 0.7 else "text"
                except Exception:
                    col_hints[col] = "text"

        return jsonify({
            "columns":   list(df.columns),
            "col_hints": col_hints,
            "row_count": len(df),
            "col_count": len(df.columns),
            "preview":   df.head(5).fillna("").to_dict(orient="records"),
        })
    except Exception as e:
        return jsonify({"error": f"Upload failed: {str(e)}", "detail": traceback.format_exc()}), 500


@app.route("/api/assess", methods=["POST"])
def assess():
    data = request.get_json(force=True)

    table_name         = data.get("table_name", "Unnamed Table")
    governance_answers = data.get("governance_answers", {})
    csv_content        = data.get("csv_content")
    column_standards   = data.get("column_standards", {})
    column_flags       = data.get("column_flags", {})

    governance_answers = {k: int(v) for k, v in governance_answers.items() if v is not None}

    try:
        gov_result = calculate_governance_score(governance_answers)
    except Exception as e:
        return jsonify({"error": f"Governance scoring failed: {e}"}), 500

    prof_result     = None
    profiling_error = None

    if csv_content:
        try:
            df          = pd.read_csv(io.StringIO(csv_content))
            prof_result = profile_dataframe(df, column_standards, column_flags)
        except Exception as e:
            profiling_error = f"{type(e).__name__}: {str(e)}"
            app.logger.error(f"Profiling failed:\n{traceback.format_exc()}")
    else:
        profiling_error = "No CSV content received by server"

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
        "profiling_error": profiling_error,
        "combined":        combined,
        "tier":            tier,
        "recommendations": recs,
    })


@app.route("/api/report", methods=["POST"])
def create_report():
    data = request.get_json(force=True)
    try:
        pdf_buf    = generate_pdf_report(data)
        table_name = data.get("table_name", "report").replace(" ", "_")
        return send_file(
            pdf_buf,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"DQ_Assessment_{table_name}.pdf",
        )
    except Exception as e:
        return jsonify({"error": f"PDF generation failed: {e}", "detail": traceback.format_exc()}), 500


if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") != "production"
    print(f"\n  Data Quality Assessment Tool — http://localhost:{port}\n")
    app.run(debug=debug, host="0.0.0.0", port=port)
