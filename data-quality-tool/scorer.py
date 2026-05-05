# =============================================================================
# DATA QUALITY ASSESSMENT TOOL – SCORING ENGINE
# =============================================================================
# This module converts raw governance answers and profiling output into a
# single weighted maturity score and assigns a Gold / Silver / Bronze tier.
#
# All weights and thresholds are imported from config.py so they can be
# adjusted in one place without touching this file.
#
# Call order expected by app.py:
#   1. calculate_governance_score(answers)      → governance result dict
#   2. calculate_combined_score(gov, prof)       → combined result dict
#   3. get_tier(combined_score)                  → tier dict
#   4. get_recommendations(gov, prof, tier)      → list of recommendation dicts
# =============================================================================

from __future__ import annotations  # Allows forward-referenced type hints on Python 3.9
from typing import Dict, Any, List, Optional  # Type aliases for readability and IDE support

# Import all configurable weights and thresholds from the central config file.
# Changing these values in config.py is the only way to retune scoring behaviour.
from config import (
    GOVERNANCE_WEIGHT,             # Fraction of combined score from governance (e.g. 0.60)
    PROFILING_WEIGHT,              # Fraction of combined score from profiling (e.g. 0.40)
    TIER_GOLD,                     # Minimum combined score to earn Gold tier (e.g. 80)
    TIER_SILVER,                   # Minimum combined score to earn Silver tier (e.g. 60)
    GOVERNANCE_DIMENSION_WEIGHTS,  # Per-dimension weights for the governance score
    PROFILING_DIMENSION_WEIGHTS,   # Per-dimension weights for the profiling score (unused here but imported for completeness)
)

# Import the question list and display labels to drive the scoring loop.
# QUESTIONS provides the dimension mapping for each question ID.
# DIMENSION_LABELS provides human-readable names for each dimension key.
from questions import QUESTIONS, DIMENSION_LABELS


# =============================================================================
# Governance scoring
# =============================================================================

def calculate_governance_score(answers: Dict[str, int]) -> Dict[str, Any]:
    """
    Convert raw questionnaire answers into a 0–100 governance score.

    Args:
        answers: Dict mapping question IDs to maturity values (1–4).
                 Example: {"q1": 3, "q2": 2, "q3": 4, ...}
                 Unanswered questions are simply omitted (not penalised).

    Returns a dict containing:
        overall          – weighted combined governance score (0–100)
        dimension_scores – per-dimension 0–100 average score
        dimension_labels – human-readable dimension names (from DIMENSION_LABELS)
        question_scores  – per-question normalised scores (0–100)
        answered_count   – number of questions that received an answer
        max_questions    – total questions in the questionnaire
        raw_answers      – echo of the input dict (for PDF report use)
    """
    # question_scores will hold the normalised (0–100) score for each answered question.
    # Key = question ID (e.g. "q1"), value = normalised float.
    question_scores: Dict[str, float] = {}

    # dimension_totals accumulates normalised scores per dimension so we can
    # average them later.  Pre-populate with empty lists for each known dimension
    # so dimensions with zero answers still appear in the output as 0.0.
    dimension_totals: Dict[str, List[float]] = {d: [] for d in GOVERNANCE_DIMENSION_WEIGHTS}

    # Iterate through every question in the defined questionnaire order.
    for q in QUESTIONS:
        qid = q["id"]          # Question identifier, e.g. "q1"
        dim = q["dimension"]   # Dimension this question belongs to, e.g. "governance_ownership"

        # Look up the user's answer for this question.  Returns None if unanswered.
        value = answers.get(qid)

        if value is None:
            continue  # Skip unanswered questions; they don't contribute to the score

        # Normalise the 1–4 maturity value to a 0–100 scale:
        #   value=1 → (1-1)/3 * 100 = 0.0   (ad hoc / none)
        #   value=2 → (2-1)/3 * 100 = 33.3  (informal)
        #   value=3 → (3-1)/3 * 100 = 66.7  (defined)
        #   value=4 → (4-1)/3 * 100 = 100.0 (optimised)
        normalised = (int(value) - 1) / 3 * 100

        question_scores[qid] = round(normalised, 2)  # Store rounded score for this question

        # Append normalised score to its dimension bucket for later averaging.
        if dim in dimension_totals:
            dimension_totals[dim].append(normalised)

    # Compute the average normalised score for each dimension.
    # If no questions in a dimension were answered, that dimension scores 0.0.
    dimension_scores: Dict[str, float] = {}
    for dim, scores in dimension_totals.items():
        # sum(scores) / len(scores) = simple average; guard against empty list with 0.0 default
        dimension_scores[dim] = round(sum(scores) / len(scores), 2) if scores else 0.0

    # Compute the overall governance score as a weighted sum of dimension averages.
    # Each dimension average is multiplied by its weight from GOVERNANCE_DIMENSION_WEIGHTS.
    # Because the weights sum to 1.0, the result is a weighted average in 0–100.
    overall = sum(
        dimension_scores.get(dim, 0.0) * weight          # dimension average × weight
        for dim, weight in GOVERNANCE_DIMENSION_WEIGHTS.items()
    )

    return {
        "overall":          round(overall, 2),          # Final governance score, rounded to 2 d.p.
        "dimension_scores": dimension_scores,            # Per-dimension 0–100 averages
        "dimension_labels": DIMENSION_LABELS,            # Human-readable labels for each dimension key
        "question_scores":  question_scores,             # Per-question normalised scores
        "answered_count":   len(question_scores),        # How many questions the user actually answered
        "max_questions":    len(QUESTIONS),              # Total possible questions (20)
        "raw_answers":      answers,                     # Original 1–4 answers echoed for the PDF report
    }


# =============================================================================
# Combined scoring
# =============================================================================

def calculate_combined_score(
    governance_score: float,          # 0–100 score from calculate_governance_score()
    profiling_score: Optional[float], # 0–100 score from profiler.profile_dataframe(), or None
) -> Dict[str, Any]:
    """
    Blend governance and profiling scores using the weights in config.py.

    If no profiling score is available (user skipped CSV upload), the function
    falls back to 100 % governance weighting so the combined score still reflects
    the full 0–100 range rather than being artificially capped.

    Returns a dict containing:
        governance_score        – the input governance score
        profiling_score         – the input profiling score (or None)
        governance_contribution – governance_score × effective governance weight
        profiling_contribution  – profiling_score  × effective profiling weight (0 if None)
        combined_score          – final blended 0–100 score
        weights_used            – the actual weights applied (may differ from config if no profiling)
    """
    if profiling_score is None:
        # No CSV was uploaded — fall back to governance-only scoring.
        # Both weights are overridden: governance = 1.0, profiling = 0.0
        gov_w, pro_w = 1.0, 0.0
        combined = governance_score  # Combined score equals governance score directly
    else:
        # Normal path: both streams available — use the configured split
        gov_w = GOVERNANCE_WEIGHT    # e.g. 0.60
        pro_w = PROFILING_WEIGHT     # e.g. 0.40
        # Weighted average: each score multiplied by its weight, then summed
        combined = governance_score * gov_w + profiling_score * pro_w

    return {
        "governance_score":        round(governance_score, 2),                              # Input gov score
        "profiling_score":         round(profiling_score, 2) if profiling_score is not None else None,
        "governance_contribution": round(governance_score * gov_w, 2),                      # Points gov contributed
        "profiling_contribution":  round((profiling_score or 0) * pro_w, 2),                # Points profiling contributed (0 if None)
        "combined_score":          round(combined, 2),                                       # Final blended score
        "weights_used": {
            "governance": gov_w,   # Effective governance weight (1.0 in governance-only mode)
            "profiling":  pro_w,   # Effective profiling weight  (0.0 in governance-only mode)
        },
    }


# =============================================================================
# Tier assignment
# =============================================================================

def get_tier(combined_score: float) -> Dict[str, Any]:
    """
    Map a combined 0–100 score to a Gold / Silver / Bronze quality tier.

    Thresholds are defined in config.py:
        Gold   ≥ TIER_GOLD   (default 80)
        Silver ≥ TIER_SILVER (default 60)
        Bronze < TIER_SILVER

    Returns a dict containing:
        tier           – lowercase key ("gold", "silver", "bronze")
        label          – display label ("Gold", "Silver", "Bronze")
        colour         – hex colour for the tier badge in the UI
        description    – human-readable interpretation of the tier
        next_tier      – name of the next tier up (None if already Gold)
        points_to_next – how many points are needed to reach the next tier
        thresholds     – the three threshold values (for display in PDF footer)
    """
    if combined_score >= TIER_GOLD:
        # Score meets or exceeds the Gold threshold
        tier  = "gold"
        label = "Gold"
        colour = "#C9A84C"  # Golden amber hex colour
        description = (
            "This dataset demonstrates strong data management maturity. "
            "Governance structures, quality controls, and technical standards "
            "are well-established and actively maintained."
        )
        next_tier      = None   # Already at the top tier — no higher tier to aim for
        points_to_next = 0      # Zero points needed (already achieved)

    elif combined_score >= TIER_SILVER:
        # Score is between TIER_SILVER and TIER_GOLD
        tier  = "silver"
        label = "Silver"
        colour = "#8A8A8A"  # Mid-grey hex colour
        description = (
            "This dataset shows a defined level of data management maturity. "
            "Core governance and quality practices are in place but there are "
            "opportunities to move towards a more optimised, enforced posture."
        )
        next_tier      = "Gold"                              # The next tier to aim for
        points_to_next = round(TIER_GOLD - combined_score, 1)  # Gap between current score and Gold threshold

    else:
        # Score is below TIER_SILVER — Bronze by default
        tier  = "bronze"
        label = "Bronze"
        colour = "#A0522D"  # Sienna brown hex colour
        description = (
            "This dataset is at an early stage of data management maturity. "
            "Significant improvements are needed across governance, quality "
            "management, and technical data standards to increase trustworthiness."
        )
        next_tier      = "Silver"                              # The next tier to aim for
        points_to_next = round(TIER_SILVER - combined_score, 1)  # Gap between current score and Silver threshold

    return {
        "tier":           tier,            # Internal key used by templates and PDF
        "label":          label,           # Display name shown in the UI and report
        "colour":         colour,          # Hex colour for badge, icon, and chart colouring
        "description":    description,     # Narrative description of the tier meaning
        "next_tier":      next_tier,       # Name of the next tier (None if Gold)
        "points_to_next": points_to_next,  # Points required to reach the next tier
        "thresholds": {
            "gold":   TIER_GOLD,           # Minimum score for Gold (for display in PDF footer)
            "silver": TIER_SILVER,         # Minimum score for Silver
            "bronze": 0,                   # Bronze starts at 0 (any score below Silver)
        },
    }


# =============================================================================
# Improvement recommendations
# =============================================================================

def get_recommendations(
    governance_result: Dict[str, Any],           # Full dict from calculate_governance_score()
    profiling_result: Optional[Dict[str, Any]],  # Full dict from profiler.profile_dataframe(), or None
    tier_result: Dict[str, Any],                 # Full dict from get_tier() (not used directly here)
) -> List[Dict[str, str]]:
    """
    Generate ranked improvement recommendations based on the lowest-scoring areas.

    Logic:
    1. Sort governance dimensions by score ascending (worst first).
    2. Take the 3 lowest-scoring governance dimensions where score < 75.
    3. If profiling data exists, take the 2 lowest-scoring profiling dimensions where score < 80.
    4. Combine both lists, sort by priority (high before medium) then score (lowest first).
    5. Return the top 6 recommendations.

    Each recommendation dict contains:
        area     – display name of the scoring area
        source   – "governance" or "profiling"
        score    – the dimension's current score (0–100)
        priority – "high" (score < 40 or < 50) or "medium"
        action   – specific, actionable improvement text
    """
    recs: List[Dict[str, str]] = []  # Accumulates recommendation dicts

    # ── Governance recommendations ────────────────────────────────────────────
    # Extract dimension scores dict from the governance result
    dim_scores = governance_result.get("dimension_scores", {})

    # Sort dimensions by score ascending so the weakest areas appear first
    sorted_dims = sorted(dim_scores.items(), key=lambda x: x[1])

    # Examine the 3 worst-scoring governance dimensions
    for dim, score in sorted_dims[:3]:
        if score < 75:  # Only recommend if there is meaningful room for improvement
            label = DIMENSION_LABELS.get(dim, dim)  # Readable name; fall back to key if not found
            recs.append({
                "area":     label,
                "source":   "governance",
                "score":    round(score, 1),
                # Mark as high priority if score is below 40 (ad hoc / very early stage)
                "priority": "high" if score < 40 else "medium",
                # Look up the canned improvement action text for this dimension
                "action":   _governance_rec(dim, score),
            })

    # ── Profiling recommendations ─────────────────────────────────────────────
    if profiling_result:  # Only run if a CSV was uploaded and profiled
        prof_dims = profiling_result.get("dimensions", {})  # Dict of dimension_key → detail dict

        # Sort profiling dimensions by score ascending
        sorted_prof = sorted(prof_dims.items(), key=lambda x: x[1].get("score", 0))

        # Examine the 2 worst-scoring profiling dimensions
        for dim, detail in sorted_prof[:2]:
            score = detail.get("score", 0)  # Extract numerical score from detail dict
            if score < 80:  # Only recommend if score has room to improve
                recs.append({
                    "area":     dim.title(),   # Capitalise e.g. "completeness" → "Completeness"
                    "source":   "profiling",
                    "score":    round(score, 1),
                    # High priority if score is critically low (below 50)
                    "priority": "high" if score < 50 else "medium",
                    "action":   _profiling_rec(dim, detail),
                })

    # Sort combined list: high-priority items first, then by score ascending within each priority band
    recs.sort(key=lambda r: (0 if r["priority"] == "high" else 1, r["score"]))

    return recs[:6]  # Cap at 6 recommendations to keep the report readable


def _governance_rec(dimension: str, score: float) -> str:
    """
    Return a canned improvement action string for a governance dimension.
    The score parameter is accepted for potential future conditional logic
    but is not currently used (the action is the same regardless of how bad the score is).
    """
    recs = {
        "governance_ownership": (
            "Formally assign a Data Owner and Data Steward. Document their "
            "responsibilities and link them to a data governance policy."
        ),
        "quality_management": (
            "Define and document data quality rules. Implement automated "
            "monitoring and a formal issue escalation and remediation process."
        ),
        "lineage_documentation": (
            "Build a data dictionary and document end-to-end lineage in a "
            "data catalogue. Introduce formal change management for schema updates."
        ),
        "security_access": (
            "Classify data sensitivity and implement role-based access controls. "
            "Identify PII, apply masking/encryption, and enable audit logging."
        ),
        "training_compliance": (
            "Introduce mandatory data entry training for source system users. "
            "Implement technical validation controls and document applicable "
            "regulatory requirements."
        ),
    }
    # Look up the dimension's action text; fall back to a generic message if the key isn't found
    return recs.get(dimension, "Review and improve practices in this area.")


def _profiling_rec(dimension: str, detail: Dict[str, Any]) -> str:
    """
    Return a canned improvement action string for a profiling dimension.
    The detail dict is accepted for potential future conditional logic
    (e.g. referencing specific columns) but is not currently used.
    """
    recs = {
        "completeness": (
            "Address null values by reviewing mandatory field rules in source "
            "systems and implementing NOT NULL constraints where appropriate."
        ),
        "uniqueness": (
            "Investigate and remove duplicate records. Introduce unique key "
            "constraints or deduplication processes in the data pipeline."
        ),
        "validity": (
            "Review values that fail standard checks and correct at source. "
            "Implement reference data validation and input controls."
        ),
        "consistency": (
            "Standardise data formats and enforce consistent data types. "
            "Apply data standardisation transformations in the ETL pipeline."
        ),
        "timeliness": (
            "Review the data refresh cadence. Ensure date fields reflect "
            "current data and implement SLA-based data freshness monitoring."
        ),
    }
    # Look up the dimension's action; fall back to a generic message for unknown dimensions
    return recs.get(dimension, "Investigate and address issues in this quality dimension.")
