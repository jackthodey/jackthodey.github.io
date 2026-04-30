# =============================================================================
# DATA QUALITY ASSESSMENT TOOL – CONFIGURATION
# =============================================================================

# --- TOP-LEVEL SPLIT ---------------------------------------------------------
GOVERNANCE_WEIGHT = 0.60
PROFILING_WEIGHT  = 0.40

# --- TIER THRESHOLDS ---------------------------------------------------------
TIER_GOLD   = 80
TIER_SILVER = 60

# --- GOVERNANCE DIMENSION WEIGHTS --------------------------------------------
GOVERNANCE_DIMENSION_WEIGHTS = {
    "governance_ownership":  0.25,
    "quality_management":    0.25,
    "lineage_documentation": 0.20,
    "security_access":       0.20,
    "training_compliance":   0.10,
}

# --- PROFILING DIMENSION WEIGHTS BY DATA USE TYPE ----------------------------
# Each type adjusts the relative importance of completeness, uniqueness and
# validity to reflect what matters most for that kind of dataset.
# All weights within a type must sum to 1.0.
DATA_USE_TYPE_WEIGHTS = {
    "analytical": {          # Reporting, dashboards, BI
        "completeness": 0.40,
        "uniqueness":   0.25,
        "validity":     0.35,
    },
    "operational": {         # Live transactional / system-of-record data
        "completeness": 0.30,
        "uniqueness":   0.35,
        "validity":     0.35,
    },
    "survey": {              # Collected / self-reported responses
        "completeness": 0.50,
        "uniqueness":   0.15,
        "validity":     0.35,
    },
    "reference": {           # Lookup tables, master data, code lists
        "completeness": 0.30,
        "uniqueness":   0.45,
        "validity":     0.25,
    },
    "regulatory": {          # Compliance submissions, regulatory reporting
        "completeness": 0.30,
        "uniqueness":   0.15,
        "validity":     0.55,
    },
}

# Display labels for each type
DATA_USE_TYPE_LABELS = {
    "analytical": "Analytical",
    "operational": "Operational",
    "survey": "Survey / Research",
    "reference": "Reference / Master",
    "regulatory": "Regulatory",
}

# Default if no type is sent
DEFAULT_DATA_USE_TYPE = "analytical"

# Fall-back weights (matches the analytical profile)
PROFILING_DIMENSION_WEIGHTS = DATA_USE_TYPE_WEIGHTS[DEFAULT_DATA_USE_TYPE]

# --- PROFILING QUALITY TARGETS -----------------------------------------------
COMPLETENESS_TARGET = 0.95
UNIQUENESS_TARGET   = 0.90
VALIDITY_TARGET     = 0.95
