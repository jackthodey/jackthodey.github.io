# =============================================================================
# FAMILY QUIZ TOOL – FLASK APPLICATION
# =============================================================================
"""Family members mark their own paper quiz right/wrong, pick their name and
the quiz's week-ending date, and the tool tallies scores, a weekly
leaderboard, and a "best of" combined family score (a question counts as a
team win if at least one family member got it right).
"""
from __future__ import annotations

import re

from flask import Flask, jsonify, render_template, request

import db
from config import PLAYERS, QUESTION_COUNT
from scorer import combined_score, tally

app = Flask(__name__)
app.secret_key = "family-quiz-local-secret-change-if-shared"

_WEEK_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

db.init_db()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/config", methods=["GET"])
def get_config():
    return jsonify({"players": PLAYERS, "question_count": QUESTION_COUNT})


@app.route("/api/submission/<week_id>/<name>", methods=["GET"])
def existing_submission(week_id: str, name: str):
    if not _WEEK_ID_RE.match(week_id) or name not in PLAYERS:
        return jsonify({"error": "Invalid week or family member"}), 400
    submission = db.get_submission(week_id, name)
    if not submission:
        return jsonify({"existing": None})
    return jsonify({"existing": {
        "results": submission["results"],
        "score": submission["score"],
        "total": submission["total"],
    }})


@app.route("/api/submission/<week_id>/<name>", methods=["DELETE"])
def clear_submission(week_id: str, name: str):
    if not _WEEK_ID_RE.match(week_id) or name not in PLAYERS:
        return jsonify({"error": "Invalid week or family member"}), 400
    db.delete_submission(week_id, name)
    return jsonify({"cleared": True})


@app.route("/api/submit", methods=["POST"])
def submit():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    week_id = (data.get("week_id") or "").strip()
    results = data.get("results")

    if name not in PLAYERS:
        return jsonify({"error": "Please select a valid family member"}), 400
    if not _WEEK_ID_RE.match(week_id):
        return jsonify({"error": "Please pick a valid week-ending date"}), 400
    if not isinstance(results, list) or not results or len(results) > 200:
        return jsonify({"error": "Results must be a list of right/wrong answers"}), 400

    results = [bool(r) for r in results]
    summary = tally(results)
    db.save_submission(week_id, name, results, summary["score"], summary["total"])

    return jsonify({
        "week_id": week_id,
        "name": name,
        "score": summary["score"],
        "total": summary["total"],
    })


@app.route("/api/results/<week_id>", methods=["GET"])
def results(week_id: str):
    if not _WEEK_ID_RE.match(week_id):
        return jsonify({"error": "Invalid week"}), 400

    submissions = db.get_week_submissions(week_id)
    weekly = [{
        "name": s["name"],
        "score": s["score"],
        "total": s["total"],
        "submitted_at": s["submitted_at"],
    } for s in submissions]

    family = None
    if submissions:
        question_count = max(s["total"] for s in submissions)
        family = combined_score(question_count, submissions)

    return jsonify({
        "week_id": week_id,
        "weekly": weekly,
        "submitted_count": len(submissions),
        "player_count": len(PLAYERS),
        "family": family,
    })


@app.route("/api/weeks", methods=["GET"])
def weeks():
    return jsonify({"weeks": db.get_recent_weeks()})


@app.route("/api/leaderboard", methods=["GET"])
def leaderboard():
    return jsonify({"leaderboard": db.get_leaderboard()})


if __name__ == "__main__":
    app.run(debug=True, port=5001)
