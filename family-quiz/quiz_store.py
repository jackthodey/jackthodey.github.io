# =============================================================================
# FAMILY QUIZ TOOL – QUIZ LOADING
# =============================================================================
"""Loads weekly quizzes from JSON files in data/quizzes/.

Each file is named by its quiz id (e.g. "2026-06-07.json") and contains:
{
  "id": "2026-06-07",
  "title": "Family Quiz - 7 June 2026",
  "questions": [
    {"id": 1, "text": "...", "type": "mcq", "options": ["A", "B", "C", "D"], "answer": "B"},
    {"id": 2, "text": "...", "type": "text", "answer": "Canberra"}
  ]
}

The most recent quiz (by id, sorted descending) is treated as the "current"
quiz that the live tool serves to players.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from config import QUIZ_DIR


def _load(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_quizzes() -> List[Dict]:
    """Returns all quizzes, most recent first."""
    if not os.path.isdir(QUIZ_DIR):
        return []
    quizzes = []
    for name in os.listdir(QUIZ_DIR):
        if name.endswith(".json"):
            try:
                quizzes.append(_load(os.path.join(QUIZ_DIR, name)))
            except (json.JSONDecodeError, OSError):
                continue
    quizzes.sort(key=lambda q: q.get("id", ""), reverse=True)
    return quizzes


def get_current_quiz() -> Optional[Dict]:
    quizzes = list_quizzes()
    return quizzes[0] if quizzes else None


def get_quiz(quiz_id: str) -> Optional[Dict]:
    path = os.path.join(QUIZ_DIR, f"{quiz_id}.json")
    if not os.path.isfile(path):
        return None
    try:
        return _load(path)
    except (json.JSONDecodeError, OSError):
        return None


def public_questions(quiz: Dict) -> List[Dict]:
    """Strips answer keys so they aren't sent to the browser before grading."""
    out = []
    for q in quiz.get("questions", []):
        item = {"id": q["id"], "text": q["text"], "type": q.get("type", "mcq")}
        if item["type"] == "mcq":
            item["options"] = q.get("options", [])
        out.append(item)
    return out
