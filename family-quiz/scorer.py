# =============================================================================
# FAMILY QUIZ TOOL – GRADING
# =============================================================================
"""Grading for both multiple-choice and free-text answers.

Free-text trivia answers ("The Great Pyramid of Giza", "Maltese and English")
rarely get typed back verbatim, so matching is done on significant words
rather than exact strings: a question is correct if every significant word of
*any* accepted phrasing (the canonical `answer` plus optional `accepted`
aliases) appears somewhere in the player's answer, regardless of word order,
case, punctuation or filler words ("the", "a", "of", ...).
"""
from __future__ import annotations

import re
from typing import Dict, List

_STOPWORDS = {
    "the", "a", "an", "of", "in", "to", "and", "or", "is", "are", "was", "were",
    "be", "than", "that", "it", "its", "on", "at", "as", "with", "for", "by",
}


def _tokens(value) -> List[str]:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return [t for t in text.split() if t]


def _significant(tokens: List[str]) -> set:
    sig = {t for t in tokens if t not in _STOPWORDS}
    return sig or set(tokens)


def _alias_matches(given_tokens: set, alias) -> bool:
    alias_sig = _significant(_tokens(alias))
    return bool(alias_sig) and alias_sig.issubset(given_tokens)


def is_correct(question: Dict, given_answer) -> bool:
    given_tokens = set(_tokens(given_answer))
    if not given_tokens:
        return False
    aliases = [question.get("answer")] + list(question.get("accepted", []))
    return any(_alias_matches(given_tokens, alias) for alias in aliases if alias)


def display_answer(question: Dict) -> str:
    return question.get("display_answer") or question.get("answer")


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
            "correct_answer": display_answer(q),
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
            "correct_answer": display_answer(q),
            "correct": correct,
            "solved_by": solvers,
        })
    return {"score": score, "total": len(quiz.get("questions", [])), "breakdown": breakdown}
