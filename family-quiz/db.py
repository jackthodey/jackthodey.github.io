# =============================================================================
# FAMILY QUIZ TOOL – RESULT STORAGE (SQLite)
# =============================================================================
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, List, Optional

from config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    week_id      TEXT NOT NULL,
    name         TEXT NOT NULL,
    results      TEXT NOT NULL,
    score        INTEGER NOT NULL,
    total        INTEGER NOT NULL,
    submitted_at TEXT NOT NULL,
    UNIQUE(week_id, name)
);
"""


@contextmanager
def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute(_SCHEMA)


def save_submission(week_id: str, name: str, results: List[bool], score: int, total: int) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT INTO submissions (week_id, name, results, score, total, submitted_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(week_id, name) DO UPDATE SET
                   results=excluded.results,
                   score=excluded.score,
                   total=excluded.total,
                   submitted_at=excluded.submitted_at""",
            (week_id, name, json.dumps(results), score, total,
             datetime.now(timezone.utc).isoformat()),
        )


def get_week_submissions(week_id: str) -> List[Dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM submissions WHERE week_id = ? ORDER BY score DESC, submitted_at ASC",
            (week_id,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_recent_weeks(limit: int = 12) -> List[str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT week_id FROM submissions ORDER BY week_id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [r["week_id"] for r in rows]


def get_leaderboard() -> List[Dict]:
    """Aggregated all-time standings: total points, weeks played, average %."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT name,
                      COUNT(*)        AS weeks_played,
                      SUM(score)      AS total_score,
                      SUM(total)      AS total_possible
               FROM submissions
               GROUP BY name
               ORDER BY (CAST(SUM(score) AS REAL) / SUM(total)) DESC""",
        ).fetchall()
    leaderboard = []
    for r in rows:
        pct = (r["total_score"] / r["total_possible"] * 100) if r["total_possible"] else 0
        leaderboard.append({
            "name": r["name"],
            "weeks_played": r["weeks_played"],
            "total_score": r["total_score"],
            "total_possible": r["total_possible"],
            "average_pct": round(pct, 1),
        })
    return leaderboard


def _row_to_dict(row: sqlite3.Row) -> Dict:
    return {
        "week_id": row["week_id"],
        "name": row["name"],
        "results": json.loads(row["results"]),
        "score": row["score"],
        "total": row["total"],
        "submitted_at": row["submitted_at"],
    }
