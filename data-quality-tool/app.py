# =============================================================================
# DATA QUALITY ASSESSMENT TOOL – FLASK APPLICATION
# =============================================================================
# This file is the HTTP server entry point.  It defines all URL routes and
# connects the browser UI (index.html) to the Python backend modules.
#
# Run locally:
#   pip install -r requirements.txt
#   python app.py
# Then open http://localhost:5000
#
# On Render (production), Gunicorn starts the app via the Procfile:
#   web: gunicorn app:app
# =============================================================================

from __future__ import annotations  # Allows e.g. Dict[str, str] type hints on Python 3.9

import io           # Used to wrap the PDF bytes buffer for send_file()
import uuid         # Used to generate a unique session_id for each uploaded CSV
import traceback    # Used to capture full stack traces in error responses for debugging
from typing import Dict  # Type alias for the in-memory CSV store dictionary

import pandas as pd  # pandas: reads CSV files into DataFrames for profiling

# Flask imports:
#   Flask          – the web application class
#   jsonify        – converts a Python dict to a JSON HTTP response
#   render_template – renders a Jinja2 HTML template from /templates/
#   request        – gives access to the incoming HTTP request body and files
#   send_file      – streams a file (the PDF) back to the browser as a download
#   session        – server-side session storage (not actively used in the stateless flow)
from flask import Flask, jsonify, render_template, request, send_file, session

# Import all application modules.  Each module handles a distinct concern:
from questions  import QUESTIONS, DIMENSION_LABELS    # Questionnaire data for /api/questions
from standards  import DATA_STANDARDS                 # Standard definitions for /api/standards
from profiler   import profile_dataframe              # CSV profiling logic
from scorer     import calculate_governance_score, calculate_combined_score, get_tier, get_recommendations
from report     import generate_pdf_report            # ReportLab PDF generator

# Create the Flask application instance.
# Flask uses __name__ to locate the templates/ and static/ folders relative
# to this file's location.
app = Flask(__name__)

# Secret key for Flask's signed cookie session.
# This tool is single-user and local; the value is arbitrary but must be set
# for Flask's session infrastructure to initialise without warnings.
app.secret_key = "dq-tool-local-secret-change-if-shared"

# Limit incoming request bodies to 32 MB.
# Without this cap, a very large CSV upload could exhaust server memory.
# 32 * 1024 * 1024 = 33,554,432 bytes = 32 MB
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024

# In-memory CSV store keyed by session ID (UUID string).
# When a user uploads a CSV, the parsed DataFrame is stored here so it can be
# retrieved by /api/assess using the session_id returned by /api/upload.
# This is a module-level dict — it persists for the lifetime of the process.
# On hosted services (e.g. Render free tier), the process may sleep and restart,
# clearing this dict; that is why the UI sends csv_content in the assess payload.
_csv_store: Dict[str, pd.DataFrame] = {}


# =============================================================================
# Page routes
# =============================================================================

@app.route("/")               # Respond to GET requests at the root URL "/"
def index():
    # Render and return the single-page HTML application.
    # Flask looks for "index.html" inside the templates/ directory.
    return render_template("index.html")


# =============================================================================
# API – metadata endpoints
# =============================================================================

@app.route("/api/questions", methods=["GET"])  # Only allows GET requests
def get_questions():
    """Return the full questionnaire structure as JSON."""
    return jsonify({
        "questions":         QUESTIONS,          # List of 20 question dicts from questions.py
        "dimension_labels":  DIMENSION_LABELS,   # Dict of dimension_key → human-readable label
    })


@app.route("/api/standards", methods=["GET"])  # Only allows GET requests
def get_standards():
    """Return available data standards grouped by category."""
    # Build a category-grouped dict so the frontend can render <optgroup> elements
    grouped: Dict[str, list] = {}  # Will be e.g. {"Contact": [...], "Numeric": [...]}

    for sid, meta in DATA_STANDARDS.items():    # Iterate every standard definition
        cat = meta.get("category", "Other")     # Get the category; default to "Other" if missing
        grouped.setdefault(cat, [])             # Create an empty list for the category if it doesn't exist yet
        grouped[cat].append({
            "id":          sid,                         # Standard identifier used as the column mapping value
            "name":        meta["name"],                # Human-readable name for the dropdown
            "description": meta["description"],         # Tooltip description
            "example":     meta.get("example", ""),    # Example values (empty string if not defined)
        })

    return jsonify(grouped)  # Return the grouped dict as JSON


# =============================================================================
# API – CSV upload and preview
# =============================================================================

@app.route("/api/upload", methods=["POST"])  # Only allows POST requests (file upload)
def upload_csv():
    """
    Accept a multipart/form-data CSV upload, parse it, store it, and return
    a preview plus column metadata.

    Returns JSON containing:
        session_id  – UUID to echo back in /api/assess to retrieve the DataFrame
        columns     – list of column names
        col_hints   – per-column type hint ("numeric", "date", "text", "empty")
        row_count   – number of data rows
        col_count   – number of columns
        preview     – first 5 rows as a list of dicts (for the UI preview table)
    """
    try:
        # Check that the request includes a file field named "file"
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400  # 400 = Bad Request

        f = request.files["file"]  # Access the uploaded file object

        # Validate that a filename is present and that it ends with ".csv"
        if not f.filename or not f.filename.lower().endswith(".csv"):
            return jsonify({"error": "Please upload a .csv file"}), 400

        # Attempt to parse the uploaded file as a CSV into a pandas DataFrame.
        # f is a file-like object so pd.read_csv() can consume it directly.
        try:
            df = pd.read_csv(f)
        except Exception as e:
            # If pandas cannot parse the file (malformed CSV, encoding issue, etc.)
            return jsonify({"error": f"Could not parse CSV: {e}"}), 400

        # Reject empty files — there is nothing to profile
        if len(df) == 0:
            return jsonify({"error": "The uploaded CSV is empty"}), 400

        # Generate a unique session identifier for this upload
        sid = str(uuid.uuid4())   # uuid4() generates a random 128-bit UUID as a hyphenated string
        _csv_store[sid] = df      # Store the DataFrame in the in-memory dict keyed by the UUID

        # Build per-column type hints to help the UI suggest the right data standard.
        # We inspect only the first 20 rows as a sample to keep this fast.
        col_hints = {}
        for col in df.columns:
            s = df[col].dropna()  # Drop nulls so type detection isn't confused by missing values

            if len(s) == 0:
                col_hints[col] = "empty"  # Column is entirely null
                continue

            # Test if the column looks numeric: try to convert the first 20 values to numbers.
            # .mean() on a boolean Series gives the proportion of successful conversions.
            if pd.to_numeric(s.head(20), errors="coerce").notna().mean() > 0.8:
                col_hints[col] = "numeric"  # More than 80 % converted → likely numeric
                continue

            # Test if the column looks like dates
            try:
                parsed = pd.to_datetime(s.head(20).astype(str), errors="coerce")
                # If more than 70 % of sample values parse as dates, classify as date
                col_hints[col] = "date" if parsed.notna().mean() > 0.7 else "text"
            except Exception:
                col_hints[col] = "text"  # Fall back to text if datetime parsing raises

        return jsonify({
            "session_id":  sid,                                                  # UUID for this upload
            "columns":     list(df.columns),                                     # Column names list
            "col_hints":   col_hints,                                            # Type hints per column
            "row_count":   len(df),                                              # Total data rows
            "col_count":   len(df.columns),                                      # Total columns
            "preview":     df.head(5).fillna("").to_dict(orient="records"),      # First 5 rows; NaN replaced with "" for JSON serialisation
        })
    except Exception as e:
        # Catch any unexpected error and return a 500 with the full stack trace
        # so it appears in logs / developer console for debugging
        return jsonify({"error": f"Upload failed: {str(e)}", "detail": traceback.format_exc()}), 500


# =============================================================================
# API – full assessment
# =============================================================================

@app.route("/api/assess", methods=["POST"])  # Only allows POST requests (JSON body)
def assess():
    """
    Run the complete data quality assessment and return the scored results.

    Expected JSON body:
    {
        "table_name":         string,            – user-provided dataset name
        "governance_answers": { "q1": 3, ... },  – answered questions (1–4 maturity values)
        "session_id":         string or null,    – UUID from /api/upload (null if no CSV)
        "column_standards":   { "col": "std" }  – column → standard_id mapping
    }

    Returns JSON containing:
        table_name, governance, profiling, combined, tier, recommendations
    """
    # Parse the request body as JSON.  force=True means Flask won't require a
    # Content-Type: application/json header — it will try to parse regardless.
    data = request.get_json(force=True)

    # Extract individual fields from the request body, providing defaults for missing fields
    table_name         = data.get("table_name", "Unnamed Table")  # Dataset name for display
    governance_answers = data.get("governance_answers", {})        # Dict of q_id → raw answer
    session_id         = data.get("session_id")                    # UUID from /api/upload, or None
    column_standards   = data.get("column_standards", {})          # Column-to-standard mapping

    # Convert answer values to integers.  The browser sends JSON numbers but they
    # may arrive as strings in some edge cases; also skip any None values
    # (unanswered questions) to avoid a TypeError in the scorer.
    governance_answers = {k: int(v) for k, v in governance_answers.items() if v is not None}

    # ── Governance scoring ────────────────────────────────────────────────────
    try:
        # Pass cleaned integer answers to the governance scorer.
        # Returns a dict with overall score, dimension scores, and per-question scores.
        gov_result = calculate_governance_score(governance_answers)
    except Exception as e:
        return jsonify({"error": f"Governance scoring failed: {e}"}), 500

    # ── Profiling (optional) ──────────────────────────────────────────────────
    prof_result = None  # Default: no profiling result if no CSV was uploaded

    if session_id and session_id in _csv_store:
        # A valid session_id was provided and the DataFrame is still in memory
        try:
            df = _csv_store[session_id]                            # Retrieve the stored DataFrame
            prof_result = profile_dataframe(df, column_standards)  # Run the 5-dimension profiling
        except Exception as e:
            # Profiling failure is non-fatal — the combined score falls back to governance-only
            prof_result = None
            app.logger.warning(f"Profiling failed: {e}\n{traceback.format_exc()}")

    # ── Combined scoring ──────────────────────────────────────────────────────
    # Blend governance and profiling scores (handles None profiling gracefully)
    combined = calculate_combined_score(
        gov_result["overall"],                                          # 0–100 governance score
        prof_result["overall_score"] if prof_result else None,          # 0–100 profiling score, or None
    )

    # Determine Gold / Silver / Bronze tier based on the combined score
    tier = get_tier(combined["combined_score"])

    # Generate improvement recommendations from the lowest-scoring areas
    recs = get_recommendations(gov_result, prof_result, tier)

    # Return the full assessment result as JSON
    return jsonify({
        "table_name":      table_name,    # Dataset name echoed back for display
        "governance":      gov_result,    # Full governance scoring result dict
        "profiling":       prof_result,   # Full profiling result dict (or null)
        "combined":        combined,      # Combined score and weights used
        "tier":            tier,          # Tier dict with label, colour, description
        "recommendations": recs,          # Ordered list of improvement actions
    })


# =============================================================================
# API – PDF report generation
# =============================================================================

@app.route("/api/report", methods=["POST"])  # Only allows POST requests (JSON body)
def create_report():
    """
    Generate a PDF report and stream it back to the browser as a download.

    Accepts the same full assessment result JSON that /api/assess returns.
    The browser posts the results dict back here rather than the server
    re-running the assessment, so no session state is needed.
    """
    data = request.get_json(force=True)  # Parse the assessment result JSON from the request body
    try:
        # generate_pdf_report() builds the PDF using ReportLab and returns an io.BytesIO buffer
        pdf_buf = generate_pdf_report(data)

        # Construct a filename from the dataset name, replacing spaces with underscores
        table_name = data.get("table_name", "report").replace(" ", "_")
        filename   = f"DQ_Assessment_{table_name}.pdf"

        # send_file() streams the BytesIO buffer as a file download.
        # mimetype="application/pdf" tells the browser it's a PDF.
        # as_attachment=True triggers a "Save As" dialog instead of opening in browser.
        # download_name sets the suggested filename for the save dialog.
        return send_file(
            pdf_buf,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        # Return a 500 error with the exception message and full stack trace
        return jsonify({"error": f"PDF generation failed: {e}", "detail": traceback.format_exc()}), 500


# =============================================================================
# Housekeeping
# =============================================================================

@app.route("/api/clear/<session_id>", methods=["DELETE"])  # DELETE method for resource cleanup
def clear_session(session_id: str):
    """
    Remove a stored DataFrame from the in-memory CSV store.

    This allows the browser to explicitly free memory after the assessment is
    complete.  Uses dict.pop(key, None) so it's a no-op if the key doesn't exist.
    """
    _csv_store.pop(session_id, None)  # Remove the key if present; ignore if already gone
    return jsonify({"ok": True})      # Confirm deletion


# =============================================================================
# Development server entry point
# =============================================================================

if __name__ == "__main__":
    # This block only runs when the file is executed directly (python app.py).
    # Gunicorn in production imports app as a module and never reaches this block.

    import os  # Standard library module for environment variable access

    # Read the PORT environment variable (set by Render/Heroku); default to 5000 locally
    port = int(os.environ.get("PORT", 5000))

    # Enable debug mode unless FLASK_ENV is explicitly set to "production".
    # Debug mode enables the auto-reloader and the interactive debugger.
    debug = os.environ.get("FLASK_ENV") != "production"

    print("\n  Data Quality Assessment Tool")
    print("  ─────────────────────────────")
    print(f"  Open http://localhost:{port} in your browser\n")

    # Start the Flask development server.
    # host="0.0.0.0" makes it reachable on the local network (not just localhost).
    app.run(debug=debug, host="0.0.0.0", port=port)
