# =============================================================================
# FAMILY QUIZ TOOL – SCORING
# =============================================================================
"""Players mark each question right/wrong themselves (against the printed
answer key), so there's nothing for the server to grade — it just tallies
results and works out the family "best of" comparison.

A submission's `results` is a list of booleans, one per question, where
`results[i]` is True if the player got question `i + 1` right.
"""
from __future__ import annotations

from typing import Dict, List


def tally(results: List[bool]) -> Dict:
    return {"score": sum(1 for r in results if r), "total": len(results)}


def combined_score(question_count: int, submissions: List[Dict]) -> Dict:
    """Best-of family score: a question counts as a win for the combined
    "team" if at least one family member got it right.

    `submissions` is a list of {"name": ..., "results": [bool, ...]}.
    """
    breakdown: List[Dict] = []
    score = 0
    for i in range(question_count):
        solvers = [s["name"] for s in submissions if i < len(s["results"]) and s["results"][i]]
        correct = bool(solvers)
        if correct:
            score += 1
        breakdown.append({"question": i + 1, "correct": correct, "solved_by": solvers})
    return {"score": score, "total": question_count, "breakdown": breakdown}
