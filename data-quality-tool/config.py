# =============================================================================
# DATA QUALITY ASSESSMENT TOOL – CONFIGURATION
# =============================================================================
# Central configuration file. All scoring weights and thresholds are defined
# here so the entire scoring model can be tuned in one place without touching
# the profiler, scorer, or app logic files.
#
# RULE: weights within each group must sum to exactly 1.0.
# The scoring functions multiply each dimension score (0–100) by its weight
# and sum the products. If weights don't sum to 1.0, the combined output will
# not sit within the 0–100 range.
# =============================================================================

# ── TOP-LEVEL SCORE SPLIT ─────────────────────────────────────────────────────
# The final "combined" score blends two independent assessment streams.
# Stream 1: Governance questionnaire – 20 multiple-choice questions measuring
#           data management maturity across 5 DAMA-DMBOK2 dimensions.
# Stream 2: CSV profiling – automated statistical analysis of the uploaded
#           data file across 5 data quality dimensions.
# Adjust these two constants to change how much each stream influences the
# final Gold / Silver / Bronze tier.

GOVERNANCE_WEIGHT = 0.60   # Questionnaire contributes 60 % of the combined score
PROFILING_WEIGHT  = 0.40   # CSV profiling contributes 40 % of the combined score
# GOVERNANCE_WEIGHT + PROFILING_WEIGHT must equal 1.0
# If no CSV is uploaded, scorer.calculate_combined_score() falls back to
# 100 % governance weighting and ignores PROFILING_WEIGHT entirely.

# ── TIER THRESHOLDS ───────────────────────────────────────────────────────────
# Combined scores (0–100) are bucketed into three quality tiers.
# scorer.get_tier() checks thresholds in descending order:
#   combined_score >= TIER_GOLD   → Gold   (strong, actively managed data)
#   combined_score >= TIER_SILVER → Silver (developing governance posture)
#   combined_score <  TIER_SILVER → Bronze (early-stage, largely ad hoc)

TIER_GOLD   = 80   # Score of 80 or above earns a Gold tier rating
TIER_SILVER = 60   # Score of 60–79 earns Silver; anything below 60 is Bronze

# ── GOVERNANCE DIMENSION WEIGHTS ─────────────────────────────────────────────
# The 20 governance questions are split into 5 DAMA-DMBOK2 dimensions (4 each).
# scorer.calculate_governance_score() averages the 4 question scores within
# each dimension, then multiplies that dimension average by its weight below.
# The five weighted dimension averages are then summed to give the governance score.
# Ownership and Quality Management are weighted most heavily (25 % each)
# because they underpin all other governance practices.

GOVERNANCE_DIMENSION_WEIGHTS = {
    "governance_ownership":  0.25,   # Q1–Q4  : Data owner, steward, purpose doc, governance policy
    "quality_management":    0.25,   # Q5–Q8  : DQ rules, monitoring, issue escalation, formal assessment
    "lineage_documentation": 0.20,   # Q9–Q12 : Data lineage, data dictionary, change management, glossary
    "security_access":       0.20,   # Q13–Q16: Data classification, RBAC, PII handling, audit logging
    "training_compliance":   0.10,   # Q17–Q20: User training, source controls, regulation, retention policy
}
# Sum check: 0.25 + 0.25 + 0.20 + 0.20 + 0.10 = 1.00 ✓

# ── PROFILING DIMENSION WEIGHTS ───────────────────────────────────────────────
# profiler.profile_dataframe() produces a 0–100 score for each dimension listed
# below. These weights blend those five scores into a single profiling score.
# Completeness and Validity carry the most weight (30 % each) because missing
# data and values that violate format standards are the most common and
# impactful data quality problems in practice.

PROFILING_DIMENSION_WEIGHTS = {
    "completeness":  0.30,   # Proportion of all cells that are non-null (30 %)
    "uniqueness":    0.20,   # Proportion of rows with no exact duplicate (20 %)
    "validity":      0.30,   # Proportion of values conforming to an assigned data standard (30 %)
    "consistency":   0.15,   # Intra-column type and format uniformity (15 %)
    "timeliness":    0.05,   # Proportion of date values within the recency window (5 %)
}
# Sum check: 0.30 + 0.20 + 0.30 + 0.15 + 0.05 = 1.00 ✓

# ── PROFILING QUALITY TARGETS ─────────────────────────────────────────────────
# Each profiling dimension converts an observed rate (0.0–1.0) into a 0–100
# score using the helper profiler._rate_to_score(rate, target):
#
#   score = min(rate / target, 1.0) * 100
#
# Interpretation:
#   • Observed rate ≥ target → score = 100 (full marks)
#   • Observed rate < target → score scales linearly toward 0
#   • Observed rate = 0      → score = 0 regardless of target
#
# Example: COMPLETENESS_TARGET = 0.95, observed completeness = 0.76
#   → score = min(0.76 / 0.95, 1.0) * 100 = 80.0

COMPLETENESS_TARGET  = 0.95   # 95 %+ of cells populated → completeness score of 100
UNIQUENESS_TARGET    = 0.90   # 90 %+ unique rows (≤10 % duplicates) → uniqueness score of 100
VALIDITY_TARGET      = 0.95   # 95 %+ of values passing their standard check → validity score of 100
CONSISTENCY_TARGET   = 0.97   # 97 %+ type-consistent values per column → consistency score of 100
TIMELINESS_DAYS      = 365    # Date values older than this many days from today count as stale
TIMELINESS_TARGET    = 0.90   # 90 %+ of date values within TIMELINESS_DAYS → timeliness score of 100
