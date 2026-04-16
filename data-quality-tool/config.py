# =============================================================================
# DATA QUALITY ASSESSMENT TOOL – CONFIGURATION
# =============================================================================
# All scoring weights and thresholds live here so they can be tuned without
# touching any other file. Weights within each group must sum to 1.0.
# =============================================================================

# --- TOP-LEVEL SPLIT ---------------------------------------------------------
# How much of the final combined score comes from each assessment stream.
GOVERNANCE_WEIGHT = 0.60   # Governance questionnaire contribution
PROFILING_WEIGHT  = 0.40   # CSV profiling contribution
# Must sum to 1.0 ↑

# --- TIER THRESHOLDS (combined score 0–100) ----------------------------------
TIER_GOLD   = 80   # score >= 80  →  Gold
TIER_SILVER = 60   # score >= 60  →  Silver
               #  score <  60  →  Bronze

# --- GOVERNANCE DIMENSION WEIGHTS --------------------------------------------
# Five DAMA-DMBOK2 dimensions; each group of 4 questions feeds one dimension.
GOVERNANCE_DIMENSION_WEIGHTS = {
    "governance_ownership":  0.25,   # Q1–Q4   – Ownership & governance policy
    "quality_management":    0.25,   # Q5–Q8   – DQ rules, monitoring, remediation
    "lineage_documentation": 0.20,   # Q9–Q12  – Lineage, data dict, change mgmt
    "security_access":       0.20,   # Q13–Q16 – Classification, RBAC, PII, audit
    "training_compliance":   0.10,   # Q17–Q20 – Training, controls, regulation
}
# Must sum to 1.0 ↑

# --- PROFILING DIMENSION WEIGHTS ---------------------------------------------
# Five GE-style quality dimensions applied to the uploaded CSV.
PROFILING_DIMENSION_WEIGHTS = {
    "completeness":  0.30,   # Non-null rate across all columns
    "uniqueness":    0.20,   # Absence of duplicate rows / unique-value ratio
    "validity":      0.30,   # % of values matching their mapped data standard
    "consistency":   0.15,   # Type/format consistency within columns
    "timeliness":    0.05,   # Recency of date/datetime columns
}
# Must sum to 1.0 ↑

# --- PROFILING QUALITY TARGETS -----------------------------------------------
# Values at or above these rates score 100 on that dimension; below scales down.
COMPLETENESS_TARGET  = 0.95   # 95% non-null  → full marks
UNIQUENESS_TARGET    = 0.90   # 90% unique rows → full marks
VALIDITY_TARGET      = 0.95   # 95% values conform to standard → full marks
CONSISTENCY_TARGET   = 0.97   # 97% type-consistent values → full marks
TIMELINESS_DAYS      = 365    # Values older than this (days) counted as stale
TIMELINESS_TARGET    = 0.90   # 90% of date values within TIMELINESS_DAYS → full marks
