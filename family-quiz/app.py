# =============================================================================
# FAMILY QUIZ TOOL – FLASK APPLICATION
# =============================================================================
from __future__ import annotations

from flask import Flask, jsonify, render_template, request

import db
import quiz_store
from config import PLAYERS
from scorer import combined_score, grade_submission

app = Flask(__name__)
app.secret_key = "family-quiz-local-secret-change-if-shared"

db.init_db()


@app.route("/")
def index():
    return render_template("index.html", players=PLAYERS)


@app.route("/api/quiz/current", methods=["GET"])
def current_quiz():
    quiz = quiz_store.get_current_quiz()
    if not quiz:
        return jsonify({"error": "No quiz has been published yet"}), 404
    return jsonify({
        "id": quiz["id"],
        "title": quiz.get("title", quiz["id"]),
        "questions": quiz_store.public_questions(quiz),
        "players": PLAYERS,
    })


@app.route("/api/submit", methods=["POST"])
def submit():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    quiz_id = (data.get("quiz_id") or "").strip()
    answers = data.get("answers") or {}

    if name not in PLAYERS:
        return jsonify({"error": "Please select a valid family member"}), 400
    if not isinstance(answers, dict):
        return jsonify({"error": "Answers must be an object of question id -> answer"}), 400

    quiz = quiz_store.get_quiz(quiz_id) if quiz_id else quiz_store.get_current_quiz()
    if not quiz:
        return jsonify({"error": "Quiz not found"}), 404

    answers = {str(k): v for k, v in answers.items()}
    result = grade_submission(quiz, answers)
    db.save_submission(quiz["id"], name, answers, result["score"], result["total"])

    return jsonify({
        "quiz_id": quiz["id"],
        "name": name,
        "score": result["score"],
        "total": result["total"],
        "breakdown": result["breakdown"],
    })


@app.route("/api/results/<quiz_id>", methods=["GET"])
def results(quiz_id: str):
    quiz = quiz_store.get_quiz(quiz_id)
    if not quiz:
        return jsonify({"error": "Quiz not found"}), 404

    submissions = db.get_quiz_submissions(quiz_id)
    weekly = [{
        "name": s["name"],
        "score": s["score"],
        "total": s["total"],
        "submitted_at": s["submitted_at"],
    } for s in submissions]

    family = None
    if submissions:
        family = combined_score(quiz, submissions)

    return jsonify({
        "quiz_id": quiz["id"],
        "title": quiz.get("title", quiz["id"]),
        "weekly": weekly,
        "submitted_count": len(submissions),
        "player_count": len(PLAYERS),
        "family": family,
    })


@app.route("/api/leaderboard", methods=["GET"])
def leaderboard():
    return jsonify({"leaderboard": db.get_leaderboard()})


if __name__ == "__main__":
    app.run(debug=True, port=5001)
