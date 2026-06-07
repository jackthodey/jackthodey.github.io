# =============================================================================
# FAMILY QUIZ TOOL – GRADING
# =============================================================================
from __future__ import annotations

from typing import Dict, List


def _normalise(value) -> str:
    return str(value).strip().lower() if value is not None else ""


def is_correct(question: Dict, given_answer) -> bool:
    return _normalise(given_answer) == _normalise(question.get("answer"))


def grade_submission(quiz: Dict, answers: Dict[str, str]) -> Dict:
    """Grades one player's answers against the quiz answer key.

    `answers` maps question id (as string) to the player's chosen/typed answer.
    Returns the score, total and a per-question breakdown.
    """
    breakdown: List[Dict] = []
    score = 0
    for q in quiz.get("questions", []):
        qid = str(q["id"])
        given = answers.get(qid)
        correct = is_correct(q, given)
        if correct:
            score += 1
        breakdown.append({
            "id": q["id"],
            "text": q["text"],
            "your_answer": given,
            "correct_answer": q.get("answer"),
            "correct": correct,
        })
    return {"score": score, "total": len(quiz.get("questions", [])), "breakdown": breakdown}


def combined_score(quiz: Dict, submissions: List[Dict]) -> Dict:
    """Best-of family score: a question counts as correct for the combined
    "team" if at least one family member answered it correctly.

    `submissions` is a list of {"name": ..., "answers": {qid: answer}}.
    """
    breakdown: List[Dict] = []
    score = 0
    for q in quiz.get("questions", []):
        qid = str(q["id"])
        solvers = [s["name"] for s in submissions if is_correct(q, s["answers"].get(qid))]
        correct = bool(solvers)
        if correct:
            score += 1
        breakdown.append({
            "id": q["id"],
            "text": q["text"],
            "correct_answer": q.get("answer"),
            "correct": correct,
            "solved_by": solvers,
        })
    return {"score": score, "total": len(quiz.get("questions", [])), "breakdown": breakdown}
