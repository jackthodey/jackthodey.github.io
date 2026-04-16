# =============================================================================
# DATA QUALITY ASSESSMENT TOOL – SCORING ENGINE
# =============================================================================
# Converts raw governance answers and profiling output into a single weighted
# maturity score and assigns a Gold / Silver / Bronze tier.
#
# All weights and thresholds are imported from config.py so they can be tuned
# in one place without touching this file.
# =============================================================================

from __future__ import annotations
from typing import Dict, Any, List, Optional

from config import (
    GOVERNANCE_WEIGHT,
    PROFILING_WEIGHT,
    TIER_GOLD,
    TIER_SILVER,
    GOVERNANCE_DIMENSION_WEIGHTS,
    PROFILING_DIMENSION_WEIGHTS,
)
from questions import QUESTIONS, DIMENSION_LABELS


# =============================================================================
# Governance scoring
# =============================================================================

def calculate_governance_score(answers: Dict[str, int]) -> Dict[str, Any]:
    """
    Score governance questionnaire answers.

    Args:
        answers: {question_id: maturity_value (1–4)}

    Returns a dict with:
        overall          – 0–100 weighted combined governance score
        dimension_scores – per-dimension 0–100 score
        question_scores  – per-question normalised score (0–100)
        answered_count   – number of questions answered
        max_questions    – total number of questions
        raw_answers      – echo of input answers
    """
    question_scores: Dict[str, float] = {}
    dimension_totals: Dict[str, List[float]] = {d: [] for d in GOVERNANCE_DIMENSION_WEIGHTS}

    for q in QUESTIONS:
        qid = q["id"]
        dim = q["dimension"]
        value = answers.get(qid)
        if value is None:
            continue
        # Normalise 1–4 to 0–100
        normalised = (int(value) - 1) / 3 * 100
        question_scores[qid] = round(normalised, 2)
        if dim in dimension_totals:
            dimension_totals[dim].append(normalised)

    # Per-dimension score (average of questions answered in that dimension)
    dimension_scores: Dict[str, float] = {}
    for dim, scores in dimension_totals.items():
        dimension_scores[dim] = round(sum(scores) / len(scores), 2) if scores else 0.0

    # Weighted overall governance score
    overall = sum(
        dimension_scores.get(dim, 0.0) * weight
        for dim, weight in GOVERNANCE_DIMENSION_WEIGHTS.items()
    )

    return {
        "overall":          round(overall, 2),
        "dimension_scores": dimension_scores,
        "dimension_labels": DIMENSION_LABELS,
        "question_scores":  question_scores,
        "answered_count":   len(question_scores),
        "max_questions":    len(QUESTIONS),
        "raw_answers":      answers,
    }


# =============================================================================
# Combined scoring
# =============================================================================

def calculate_combined_score(
    governance_score: float,
    profiling_score: Optional[float],
) -> Dict[str, Any]:
    """
    Combine governance and profiling scores using the configured weights.

    If no profiling score is provided (user skipped CSV upload), the combined
    score is based on governance alone and the weights are renormalised.

    Returns a dict with:
        governance_score       – 0–100
        profiling_score        – 0–100 or None
        governance_contribution – weighted governance points
        profiling_contribution  – weighted profiling points
        combined_score         – final 0–100 score
        weights_used           – the effective weights applied
    """
    if profiling_score is None:
        # Governance-only mode
        gov_w, pro_w = 1.0, 0.0
        combined = governance_score
    else:
        gov_w = GOVERNANCE_WEIGHT
        pro_w = PROFILING_WEIGHT
        combined = governance_score * gov_w + profiling_score * pro_w

    return {
        "governance_score":        round(governance_score, 2),
        "profiling_score":         round(profiling_score, 2) if profiling_score is not None else None,
        "governance_contribution": round(governance_score * gov_w, 2),
        "profiling_contribution":  round((profiling_score or 0) * pro_w, 2),
        "combined_score":          round(combined, 2),
        "weights_used": {
            "governance": gov_w,
            "profiling":  pro_w,
        },
    }


# =============================================================================
# Tier assignment
# =============================================================================

def get_tier(combined_score: float) -> Dict[str, Any]:
    """
    Map a combined score to Gold / Silver / Bronze.

    Thresholds defined in config.py:
        Gold   >= TIER_GOLD   (default 80)
        Silver >= TIER_SILVER (default 60)
        Bronze < TIER_SILVER
    """
    if combined_score >= TIER_GOLD:
        tier = "gold"
        label = "Gold"
        colour = "#C9A84C"
        description = (
            "This dataset demonstrates strong data management maturity. "
            "Governance structures, quality controls, and technical standards "
            "are well-established and actively maintained."
        )
        next_tier = None
        points_to_next = 0
    elif combined_score >= TIER_SILVER:
        tier = "silver"
        label = "Silver"
        colour = "#8A8A8A"
        description = (
            "This dataset shows a defined level of data management maturity. "
            "Core governance and quality practices are in place but there are "
            "opportunities to move towards a more optimised, enforced posture."
        )
        next_tier = "Gold"
        points_to_next = round(TIER_GOLD - combined_score, 1)
    else:
        tier = "bronze"
        label = "Bronze"
        colour = "#A0522D"
        description = (
            "This dataset is at an early stage of data management maturity. "
            "Significant improvements are needed across governance, quality "
            "management, and technical data standards to increase trustworthiness."
        )
        next_tier = "Silver"
        points_to_next = round(TIER_SILVER - combined_score, 1)

    return {
        "tier":           tier,
        "label":          label,
        "colour":         colour,
        "description":    description,
        "next_tier":      next_tier,
        "points_to_next": points_to_next,
        "thresholds": {
            "gold":   TIER_GOLD,
            "silver": TIER_SILVER,
            "bronze": 0,
        },
    }


# =============================================================================
# Improvement recommendations
# =============================================================================

def get_recommendations(
    governance_result: Dict[str, Any],
    profiling_result: Optional[Dict[str, Any]],
    tier_result: Dict[str, Any],
) -> List[Dict[str, str]]:
    """
    Generate ranked improvement recommendations based on the lowest-scoring
    areas.  Returns a list of recommendation dicts ordered by priority.
    """
    recs: List[Dict[str, str]] = []

    # Governance gaps
    dim_scores = governance_result.get("dimension_scores", {})
    sorted_dims = sorted(dim_scores.items(), key=lambda x: x[1])

    for dim, score in sorted_dims[:3]:
        if score < 75:
            label = DIMENSION_LABELS.get(dim, dim)
            recs.append({
                "area":     label,
                "source":   "governance",
                "score":    round(score, 1),
                "priority": "high" if score < 40 else "medium",
                "action":   _governance_rec(dim, score),
            })

    # Profiling gaps
    if profiling_result:
        prof_dims = profiling_result.get("dimensions", {})
        sorted_prof = sorted(prof_dims.items(), key=lambda x: x[1].get("score", 0))
        for dim, detail in sorted_prof[:2]:
            score = detail.get("score", 0)
            if score < 80:
                recs.append({
                    "area":     dim.title(),
                    "source":   "profiling",
                    "score":    round(score, 1),
                    "priority": "high" if score < 50 else "medium",
                    "action":   _profiling_rec(dim, detail),
                })

    # Sort all recommendations: high priority first, then by score ascending
    recs.sort(key=lambda r: (0 if r["priority"] == "high" else 1, r["score"]))
    return recs[:6]  # Return top 6


def _governance_rec(dimension: str, score: float) -> str:
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
    return recs.get(dimension, "Review and improve practices in this area.")


def _profiling_rec(dimension: str, detail: Dict[str, Any]) -> str:
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
    return recs.get(dimension, "Investigate and address issues in this quality dimension.")
