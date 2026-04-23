# =============================================================================
# DATA QUALITY ASSESSMENT TOOL – CONFIGURATION
# =============================================================================
# All scoring weights and thresholds live here so they can be tuned without
# touching any other file. Weights within each group must sum to 1.0.
# =============================================================================

# --- TOP-LEVEL SPLIT ---------------------------------------------------------
GOVERNANCE_WEIGHT = 0.60   # Governance questionnaire contribution
PROFILING_WEIGHT  = 0.40   # CSV profiling contribution

# --- TIER THRESHOLDS (combined score 0–100) ----------------------------------
TIER_GOLD   = 80   # score >= 80  →  Gold
TIER_SILVER = 60   # score >= 60  →  Silver
               #  score <  60  →  Bronze

# --- GOVERNANCE DIMENSION WEIGHTS --------------------------------------------
GOVERNANCE_DIMENSION_WEIGHTS = {
    "governance_ownership":  0.25,
    "quality_management":    0.25,
    "lineage_documentation": 0.20,
    "security_access":       0.20,
    "training_compliance":   0.10,
}

# --- PROFILING DIMENSION WEIGHTS ---------------------------------------------
# Only columns the user explicitly flags/maps are counted in each dimension:
#   Completeness – mandatory-flagged columns only
#   Uniqueness   – unique-flagged columns only
#   Validity     – standard-mapped columns only
PROFILING_DIMENSION_WEIGHTS = {
    "completeness": 0.40,
    "uniqueness":   0.25,
    "validity":     0.35,
}

# --- PROFILING QUALITY TARGETS -----------------------------------------------
COMPLETENESS_TARGET = 0.95   # 95% non-null in mandatory columns → full marks
UNIQUENESS_TARGET   = 0.90   # 90% unique values in flagged columns → full marks
VALIDITY_TARGET     = 0.95   # 95% of mapped values conform to standard → full marks
