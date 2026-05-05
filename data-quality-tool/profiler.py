# =============================================================================
# DATA QUALITY ASSESSMENT TOOL – PROFILING ENGINE
# =============================================================================
# Profiles a pandas DataFrame against five data-quality dimensions.
# Uses Great Expectations (GX 1.x) for formal expectation validation where
# available, with a pure-pandas fallback for environments where GX is not
# installed.
#
# Dimensions scored:
#   completeness  – proportion of cells that contain a value (non-null)
#   uniqueness    – proportion of rows that are not exact duplicates
#   validity      – proportion of values conforming to the user's assigned standard
#   consistency   – intra-column type / format uniformity
#   timeliness    – proportion of date values within the configured recency window
#
# References: DAMA-DMBOK2 Ch.13; ISO 8000-8; Great Expectations Expectations
#             Gallery (https://greatexpectations.io/expectations)
# =============================================================================

from __future__ import annotations  # Allows type hint strings to be evaluated lazily

import re        # Standard library regex — used for date/type detection in consistency check
import warnings  # Standard library — used to suppress noisy pandas deprecation warnings
from datetime import datetime, timedelta, timezone  # datetime: current time for timeliness cutoff
                                                    # timedelta: subtract days from today
                                                    # timezone: make timestamps tz-aware for comparison
from typing import Dict, List, Optional, Any  # Type aliases for function signatures

import numpy as np    # NumPy: numerical operations; not directly used but pandas depends on it
import pandas as pd   # pandas: core data manipulation library for all profiling checks

# Import scoring constants and the full weight mapping from the central config file
from config import (
    COMPLETENESS_TARGET,           # Rate at which completeness scores 100 (e.g. 0.95)
    UNIQUENESS_TARGET,             # Rate at which uniqueness scores 100  (e.g. 0.90)
    VALIDITY_TARGET,               # Rate at which validity scores 100    (e.g. 0.95)
    CONSISTENCY_TARGET,            # Rate at which consistency scores 100 (e.g. 0.97)
    TIMELINESS_DAYS,               # How many days old a date value can be before it's "stale"
    TIMELINESS_TARGET,             # Rate at which timeliness scores 100  (e.g. 0.90)
    PROFILING_DIMENSION_WEIGHTS,   # Dict of dimension_key → weight (all weights sum to 1.0)
)

# Import the data standards catalogue and its value-checking function
from standards import DATA_STANDARDS, check_value  # DATA_STANDARDS: all standard definitions
                                                    # check_value: tests one value against one standard

# Suppress pandas FutureWarning and other runtime warnings that pollute server logs
warnings.filterwarnings("ignore")

# ── Great Expectations (GX) availability flag ─────────────────────────────────
# GX is an optional dependency.  We attempt to import it at module load time.
# If it's not installed, we set the flag to False and fall back to pandas-only checks.
_GX_AVAILABLE = False  # Assume GX is not available until we confirm otherwise
try:
    import great_expectations as gx  # Try to import the GX library
    _GX_AVAILABLE = True             # Import succeeded — GX is available
except ImportError:
    pass  # ImportError means the package is not installed — silently continue


# =============================================================================
# Public entry point
# =============================================================================

def profile_dataframe(
    df: pd.DataFrame,                    # The parsed CSV as a pandas DataFrame
    column_standards: Dict[str, str],    # User's column→standard mapping {col_name: standard_id}
) -> Dict[str, Any]:
    """
    Profile *df* across five data quality dimensions and return a results dict.

    Args:
        df:               The uploaded pandas DataFrame (all rows and columns).
        column_standards: Dict mapping column names to standard IDs from
                          DATA_STANDARDS.  Columns not in this dict are still
                          checked for completeness, uniqueness, and consistency,
                          but skip the validity check.

    Returns a dict with keys:
        dimensions     – per-dimension score (0–100) and supporting detail
        overall_score  – weighted combined profiling score (0–100)
        column_stats   – per-column statistics for the UI data table
        row_count      – number of rows in the DataFrame
        col_count      – number of columns in the DataFrame
        duplicate_rows – count of exact duplicate rows
        gx_used        – bool: whether GX was used for any dimension
    """
    total_rows, total_cols = len(df), len(df.columns)  # Cache row and column counts

    if total_rows == 0:
        # Empty DataFrame — skip all checks and return zeroed-out result
        return _empty_result(total_cols)

    # ── Run pandas-based dimension checks ─────────────────────────────────────
    # Each function returns a dict with at minimum {"score": float, "description": str}
    completeness  = _check_completeness(df)
    uniqueness    = _check_uniqueness(df)
    validity      = _check_validity(df, column_standards)
    consistency   = _check_consistency(df)
    timeliness    = _check_timeliness(df, column_standards)

    # ── Optionally enrich with Great Expectations ──────────────────────────────
    gx_used = False  # Track whether GX ran successfully
    if _GX_AVAILABLE:
        try:
            # _run_gx_expectations() runs formal GX expectations and returns override values
            gx_enrichments = _run_gx_expectations(df, column_standards)

            # If GX produced a completeness override, replace our pandas calculation.
            # GX uses a different algorithm that may be more accurate for large DataFrames.
            if gx_enrichments.get("completeness_override") is not None:
                completeness["score"] = gx_enrichments["completeness_override"]

            gx_used = True  # Mark that GX ran without error
        except Exception:
            pass  # GX failed for any reason — pandas results stand; don't crash the whole profile

    # ── Assemble the dimensions dict ───────────────────────────────────────────
    dimensions = {
        "completeness": completeness,  # Non-null rate result
        "uniqueness":   uniqueness,    # Duplicate-row rate result
        "validity":     validity,      # Standard conformance result
        "consistency":  consistency,   # Type uniformity result
        "timeliness":   timeliness,    # Date recency result
    }

    # ── Compute the weighted overall profiling score ───────────────────────────
    # Each dimension's score (0–100) is multiplied by its configured weight,
    # then all products are summed.  Because the weights sum to 1.0, the result
    # is itself in the range 0–100.
    overall = sum(
        dimensions[dim]["score"] * PROFILING_DIMENSION_WEIGHTS[dim]  # score × weight for each dim
        for dim in dimensions                                          # iterate all 5 dimensions
    )

    # ── Build per-column statistics for the UI table ──────────────────────────
    column_stats = _build_column_stats(df, column_standards)

    return {
        "dimensions":     dimensions,            # Per-dimension results (score + detail)
        "overall_score":  round(overall, 2),     # Combined weighted score, rounded
        "column_stats":   column_stats,          # Per-column stats list for the UI
        "row_count":      total_rows,            # Total rows analysed
        "col_count":      total_cols,            # Total columns in the file
        "duplicate_rows": int(df.duplicated().sum()),  # Count of exact duplicate rows
        "gx_used":        gx_used,               # Whether GX enrichment was applied
    }


# =============================================================================
# Dimension checkers
# =============================================================================

def _check_completeness(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate the non-null rate across every cell in the DataFrame.

    Completeness rate = (total cells - null cells) / total cells

    Returns a result dict with:
        score        – 0–100 score derived from completeness_rate vs COMPLETENESS_TARGET
        rate         – completeness rate as a percentage (0–100)
        total_nulls  – total count of null cells across all columns
        column_rates – per-column completeness percentage
        description  – human-readable summary string
    """
    total_cells = len(df) * len(df.columns)  # Total number of cells = rows × columns

    null_counts  = df.isnull().sum()          # Series: count of nulls per column
    total_nulls  = int(null_counts.sum())     # Sum all per-column null counts for the grand total

    # Completeness rate: fraction of cells that have a value
    # Guard against division by zero if somehow total_cells is 0
    completeness_rate = (total_cells - total_nulls) / total_cells if total_cells else 0.0

    # Build per-column completeness percentages for the column stats table
    col_rates = {
        col: round((len(df) - int(null_counts[col])) / len(df) * 100, 1)  # (non-nulls / total rows) × 100
        for col in df.columns
    }

    # Convert the rate to a 0–100 score using the target threshold
    score = _rate_to_score(completeness_rate, COMPLETENESS_TARGET)

    return {
        "score":        round(score, 2),
        "rate":         round(completeness_rate * 100, 2),   # Convert 0–1 fraction to 0–100 percentage
        "total_nulls":  total_nulls,
        "column_rates": col_rates,
        "description":  f"{completeness_rate*100:.1f}% of all cells are populated",
    }


def _check_uniqueness(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate the duplicate-row rate across the entire DataFrame.

    Uniqueness rate = (total rows - duplicate rows) / total rows

    A row is counted as a duplicate if ALL its values are identical to
    another row that appeared earlier in the DataFrame (pandas default).

    Returns a result dict with:
        score             – 0–100 score vs UNIQUENESS_TARGET
        unique_row_rate   – percentage of rows that are not duplicates
        duplicate_rows    – absolute count of duplicate rows
        column_unique_pct – per-column distinct-value percentages
        description       – human-readable summary
    """
    n = len(df)  # Total row count

    # df.duplicated() returns a boolean Series: True for rows that are duplicates
    # of an earlier row.  .sum() counts how many True values there are.
    dup_count = int(df.duplicated().sum())

    # Unique row rate: fraction of rows that are NOT duplicates
    unique_row_rate = (n - dup_count) / n if n else 0.0

    # Per-column distinct value percentages — shows how varied each column's values are.
    # nunique(dropna=True) counts distinct non-null values; dividing by n gives the ratio.
    col_unique = {
        col: round(df[col].nunique(dropna=True) / n * 100, 1)
        for col in df.columns
    }

    score = _rate_to_score(unique_row_rate, UNIQUENESS_TARGET)

    return {
        "score":             round(score, 2),
        "unique_row_rate":   round(unique_row_rate * 100, 2),   # As a percentage
        "duplicate_rows":    dup_count,
        "column_unique_pct": col_unique,
        "description":       f"{dup_count} exact duplicate row(s) found "
                             f"({(1-unique_row_rate)*100:.1f}% duplication rate)",
    }


def _check_validity(
    df: pd.DataFrame,
    column_standards: Dict[str, str],  # {col_name: standard_id} — only mapped columns are checked
) -> Dict[str, Any]:
    """
    For each column that the user mapped to a data standard, test every
    non-null value against that standard using standards.check_value().

    If no columns were mapped, return a neutral score of 70 to avoid
    penalising datasets where the user hasn't set up standard mappings.

    Returns a result dict with:
        score        – 0–100 score based on average valid percentage vs VALIDITY_TARGET
        rate         – average validity percentage across mapped columns
        column_rates – per-column validity detail dicts
        unmapped_cols – columns that were NOT mapped to any standard
        description  – human-readable summary
    """
    if not column_standards:
        # No standards were mapped at all — return a neutral result
        return {
            "score":         70.0,   # Neutral score: not bad, not good
            "rate":          None,   # No rate to show (no checks ran)
            "column_rates":  {},
            "unmapped_cols": list(df.columns),  # All columns are unmapped
            "description":   "No columns mapped to standards – validity not assessed",
        }

    col_rates = {}  # Will hold per-column validity detail dicts

    for col, std_id in column_standards.items():  # Iterate each column→standard mapping
        if col not in df.columns:
            continue  # Skip if the mapped column doesn't exist in the actual CSV

        non_null = df[col].dropna()  # Remove null values — nulls are a completeness issue, not validity

        if len(non_null) == 0:
            # Column exists but all values are null — record 0% valid
            col_rates[col] = {"standard": std_id, "valid_pct": 0.0, "invalid_count": 0}
            continue

        # Test every non-null value using check_value() from standards.py.
        # check_value() returns True (valid) or False (invalid) for each value.
        # We cast to str first because check_value() expects a string.
        valid_count = sum(
            check_value(v, std_id)              # Returns True or False
            for v in non_null.astype(str).tolist()  # Convert column to list of strings
        )

        # Calculate the percentage of values that passed
        valid_pct = valid_count / len(non_null) * 100

        col_rates[col] = {
            "standard":      std_id,                                             # Standard ID
            "standard_name": DATA_STANDARDS.get(std_id, {}).get("name", std_id),  # Human-readable name
            "valid_pct":     round(valid_pct, 1),                               # Percentage valid
            "invalid_count": len(non_null) - valid_count,                        # Count of failing values
            "total_checked": len(non_null),                                      # Total values tested
        }

    if col_rates:
        # Average the validity percentages across all mapped columns
        avg_valid = sum(v["valid_pct"] for v in col_rates.values()) / len(col_rates)
    else:
        avg_valid = 70.0  # No valid col_rates entries — default to neutral

    # Convert average percentage (0–100) to a 0–1 rate before passing to _rate_to_score
    score = _rate_to_score(avg_valid / 100, VALIDITY_TARGET)

    # List all columns that were NOT mapped to any standard
    unmapped = [c for c in df.columns if c not in column_standards]

    return {
        "score":         round(score, 2),
        "rate":          round(avg_valid, 2),   # Average validity % across mapped columns
        "column_rates":  col_rates,
        "unmapped_cols": unmapped,
        "description":   f"{avg_valid:.1f}% of mapped values conform to their data standard",
    }


def _check_consistency(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Assess intra-column type and format consistency.

    For each column, the check detects what the dominant data type appears to be
    (numeric, date, or text) and measures how consistently values conform to
    that type.  Columns that contain a mix of numeric and non-numeric values
    receive a penalty, as this indicates inconsistent data entry.

    Returns a result dict with:
        score            – 0–100 score vs CONSISTENCY_TARGET
        avg_consistency  – average consistency percentage across all columns
        column_scores    – per-column consistency percentages
        description      – human-readable summary
    """
    col_scores = {}  # Will hold per-column consistency percentages

    for col in df.columns:
        series = df[col].dropna().astype(str)  # Drop nulls; cast to string for type detection

        if len(series) == 0:
            col_scores[col] = 100.0  # Empty column (all null) — no inconsistency to detect
            continue

        # ── Test for numeric type ──────────────────────────────────────────────
        # pd.to_numeric() with errors="coerce" converts non-numeric values to NaN.
        # .notna().sum() counts how many converted successfully.
        numeric_count = pd.to_numeric(series, errors="coerce").notna().sum()

        if numeric_count / len(series) >= 0.5:
            # More than 50% of values are numeric → this is a numeric column.
            # Score = the proportion of numeric values (so non-numeric outliers reduce the score)
            col_scores[col] = round(numeric_count / len(series) * 100, 1)
            continue  # Move to next column — no need to test for date or text

        # ── Test for date type ─────────────────────────────────────────────────
        # pd.to_datetime() with errors="coerce" converts unparseable values to NaT (null timestamp).
        # infer_datetime_format=True speeds up parsing by trying to detect the format from the first value.
        date_count = pd.to_datetime(series, errors="coerce", infer_datetime_format=True).notna().sum()

        if date_count / len(series) >= 0.5:
            # More than 50% parse as dates → treat as a date column
            col_scores[col] = round(date_count / len(series) * 100, 1)
            continue  # Move to next column

        # ── Text column: check case consistency ───────────────────────────────
        # For text columns, we check whether the casing style is consistent.
        # A column where all values are UPPER or all lower or all Title Case scores well.
        # Mixed casing is acceptable and doesn't penalise (dominant coverage is used).

        # Count values that are entirely uppercase (and not purely digits)
        upper_count = sum(1 for v in series if v == v.upper() and not v.isdigit())
        # Count values that are entirely lowercase
        lower_count = sum(1 for v in series if v == v.lower() and not v.isdigit())
        # Count values in Title Case (each word capitalised)
        cap_count   = sum(1 for v in series if v.istitle())

        # The dominant casing style is whichever count is highest
        dominant = max(upper_count, lower_count, cap_count)

        # Consistency = proportion of values matching the dominant casing style
        case_consistency = dominant / len(series) if len(series) else 1.0

        # ── Mixed-type penalty ─────────────────────────────────────────────────
        # If some values in a text column look numeric (5–95%) but not all,
        # this suggests inconsistent data entry (e.g. some rows have "42", others have "unknown").
        # Apply a 20-point deduction.
        mixed_penalty = 0.0
        if 0.05 < (numeric_count / len(series)) < 0.95:
            mixed_penalty = 20.0  # 20-point penalty for significant type mixing

        # Final column score: cased consistency percentage minus any mixed-type penalty
        # Clamp to [0, 100] with max/min
        col_scores[col] = max(0.0, round(min(case_consistency * 100, 100.0) - mixed_penalty, 1))

    # Average the per-column scores; if no columns (edge case), default to 100
    avg = sum(col_scores.values()) / len(col_scores) if col_scores else 100.0

    # Convert 0–100 percentage to 0–1 rate for the scoring helper
    score = _rate_to_score(avg / 100, CONSISTENCY_TARGET)

    return {
        "score":           round(score, 2),
        "avg_consistency": round(avg, 2),   # Average consistency % across all columns
        "column_scores":   col_scores,
        "description":     f"Average intra-column type/format consistency: {avg:.1f}%",
    }


def _check_timeliness(
    df: pd.DataFrame,
    column_standards: Dict[str, str],  # Used to identify columns explicitly mapped to date standards
) -> Dict[str, Any]:
    """
    Assess the recency of date/datetime column values.

    A date value is "timely" if it falls within the last TIMELINESS_DAYS days
    from the current UTC time.  Columns are identified two ways:
    1. User explicitly mapped the column to a date standard (is_date=True in DATA_STANDARDS).
    2. Auto-detection: columns whose dtype is already datetime, or whose string values
       parse as dates in more than 70% of a 50-row sample.

    If no date columns are found, returns a neutral score of 75.

    Returns a result dict with:
        score        – 0–100 score vs TIMELINESS_TARGET
        checked_cols – per date-column recency detail dicts
        description  – human-readable summary
    """
    # Calculate the cutoff timestamp: any date older than this is "stale"
    # timezone.utc ensures the comparison is tz-aware (avoids pandas tz comparison errors)
    cutoff = datetime.now(timezone.utc) - timedelta(days=TIMELINESS_DAYS)

    date_cols_checked = {}  # Will hold per-column recency detail dicts
    mapped_date_cols  = set()  # Set of column names that are date columns

    # ── Identify user-mapped date columns ─────────────────────────────────────
    # Find all standard IDs that have is_date=True in DATA_STANDARDS
    date_standard_ids = {
        sid for sid, meta in DATA_STANDARDS.items() if meta.get("is_date")
    }

    # Filter the user's column→standard mapping to only those mapping to a date standard
    mapped_date_cols = {
        col for col, sid in column_standards.items() if sid in date_standard_ids
    }

    # ── Auto-detect date columns (fallback if user didn't map any) ────────────
    if not mapped_date_cols:
        for col in df.columns:
            # Check if pandas already inferred the column as a datetime type
            if df[col].dtype in ("datetime64[ns]", "datetime64[ns, UTC]"):
                mapped_date_cols.add(col)  # Already a datetime column — include it
            elif df[col].dtype == object:  # Object dtype = likely strings
                # Take a sample of up to 50 non-null values and attempt date parsing
                sample = df[col].dropna().head(50).astype(str)
                parsed = pd.to_datetime(sample, errors="coerce", infer_datetime_format=True)
                # If more than 70% parse successfully, treat this as a date column
                if parsed.notna().sum() / max(len(sample), 1) > 0.7:
                    mapped_date_cols.add(col)

    # ── Return neutral score if no date columns found ─────────────────────────
    if not mapped_date_cols:
        return {
            "score":        75.0,   # Neutral: not penalised, but not rewarded
            "checked_cols": {},
            "description":  "No date columns detected – timeliness not assessed",
        }

    # ── Check recency for each identified date column ─────────────────────────
    for col in mapped_date_cols:
        if col not in df.columns:
            continue  # Guard: column might have been renamed or removed

        raw = df[col].dropna()  # Remove nulls before parsing

        # Parse all values to timezone-aware timestamps; non-parseable → NaT
        # utc=True ensures all timestamps get UTC timezone info for consistent comparison
        parsed = pd.to_datetime(raw, errors="coerce", infer_datetime_format=True, utc=True)

        valid_dates = parsed.dropna()  # Drop values that failed to parse as dates

        if len(valid_dates) == 0:
            continue  # No parseable dates in this column — skip

        # Count values that are within the recency window (>= cutoff timestamp)
        timely = (valid_dates >= pd.Timestamp(cutoff)).sum()

        # Calculate percentage of timely values
        timely_pct = timely / len(valid_dates) * 100

        date_cols_checked[col] = {
            "timely_pct":   round(float(timely_pct), 1),                          # % of recent values
            "oldest_value": str(valid_dates.min().date()) if len(valid_dates) else "n/a",  # Oldest date as YYYY-MM-DD
            "newest_value": str(valid_dates.max().date()) if len(valid_dates) else "n/a",  # Newest date
        }

    # ── Compute overall timeliness score ──────────────────────────────────────
    if date_cols_checked:
        # Average the timely percentages across all date columns
        avg_timely = sum(v["timely_pct"] for v in date_cols_checked.values()) / len(date_cols_checked)
        # Convert 0–100 percentage to 0–1 rate for the scoring helper
        score = _rate_to_score(avg_timely / 100, TIMELINESS_TARGET)
    else:
        # All date columns had no parseable values — fall back to neutral
        avg_timely = 75.0
        score      = 75.0

    return {
        "score":        round(score, 2),
        "checked_cols": date_cols_checked,
        "description":  f"{avg_timely:.1f}% of date values are within the last {TIMELINESS_DAYS} days",
    }


# =============================================================================
# Great Expectations enrichment
# =============================================================================

def _run_gx_expectations(
    df: pd.DataFrame,
    column_standards: Dict[str, str],
) -> Dict[str, Any]:
    """
    Run a formal GX 1.x validation pass and return override values for pandas results.

    GX is more rigorous than our pandas checks for completeness because it runs
    each column independently and accounts for edge cases.  If GX produces a
    completeness override, profile_dataframe() replaces its pandas-calculated
    completeness score with the GX value.

    Falls back gracefully (returns empty dict) if the GX API differs from expected.
    """
    # Create an ephemeral GX context — no files written to disk, lives only in memory
    context = gx.get_context(mode="ephemeral")

    # Register our DataFrame as a GX data source named "dq_source"
    ds = context.data_sources.add_pandas("dq_source")

    # Register the DataFrame as a named data asset within the source
    asset = ds.add_dataframe_asset("dq_asset")

    # Define a batch definition for the whole DataFrame (single batch, no splitting)
    batch_def = asset.add_batch_definition_whole_dataframe("dq_batch")

    # Create an expectation suite — a named collection of expectations to validate
    suite = context.suites.add(gx.ExpectationSuite(name="dq_suite"))

    # ── Add completeness expectations for every column ─────────────────────────
    for col in df.columns:
        # ExpectColumnValuesToNotBeNull: every value in this column should be non-null
        suite.add_expectation(
            gx.expectations.ExpectColumnValuesToNotBeNull(column=col)
        )

    # ── Add regex validity expectations for mapped columns ────────────────────
    for col, std_id in column_standards.items():
        if col not in df.columns:
            continue  # Skip if column is in the mapping but not in the actual DataFrame

        std     = DATA_STANDARDS.get(std_id, {})   # Look up the standard definition
        pattern = std.get("pattern")                # Get the regex pattern if one exists

        # Only add a GX regex expectation if:
        #   a) the standard has a pattern (not custom_check only), AND
        #   b) the standard does not use a custom check (GX can't run Python custom checks)
        if pattern and not std.get("custom_check"):
            flags   = std.get("flags", 0)  # Regex flags (e.g. re.IGNORECASE = 2)

            # GX accepts Python regex strings.  If IGNORECASE is set, prepend (?i) inline flag
            # because GX doesn't accept separate flags arguments.
            gx_regex = f"(?i){pattern}" if flags & re.IGNORECASE else pattern

            try:
                suite.add_expectation(
                    gx.expectations.ExpectColumnValuesToMatchRegex(
                        column=col, regex=gx_regex  # Validate each value against the standard's regex
                    )
                )
            except Exception:
                pass  # If GX rejects the expectation for any reason, silently skip it

    # Build a GX ValidationDefinition linking the batch and the expectation suite
    val_def = context.validation_definitions.add(
        gx.ValidationDefinition(
            name="dq_validation",
            data=batch_def,    # The batch (our full DataFrame)
            suite=suite,       # The expectations to validate against
        )
    )

    # Run the validation — passes the DataFrame in as a runtime batch parameter
    results = val_def.run(batch_parameters={"dataframe": df})

    # ── Extract completeness override from GX results ─────────────────────────
    # Iterate all expectation results looking for the "not null" expectations
    completeness_scores = []
    for res in results.results:
        exp_type = res.expectation_config.type  # String like "expect_column_values_to_not_be_null"
        if exp_type == "expect_column_values_to_not_be_null":
            # unexpected_percent = percentage of values that WERE null (failed the expectation)
            unexpected_pct = res.result.get("unexpected_percent", 0) or 0
            # Convert "percentage null" to "percentage complete": 100 - unexpected_pct
            completeness_scores.append(100 - unexpected_pct)

    # If we got per-column completeness scores from GX, compute their average
    override = None  # Default: no override (pandas value stands)
    if completeness_scores:
        override = round(sum(completeness_scores) / len(completeness_scores), 2)

    return {"completeness_override": override}  # Returns None if no GX completeness scores were found


# =============================================================================
# Per-column statistics (for the UI results table)
# =============================================================================

def _build_column_stats(
    df: pd.DataFrame,
    column_standards: Dict[str, str],
) -> List[Dict[str, Any]]:
    """
    Build a list of per-column statistics for rendering the data table in the UI.

    Each dict in the list represents one column and contains:
        column       – column name
        dtype        – pandas dtype string (e.g. "object", "int64", "float64")
        null_count   – count of null values
        unique_count – count of distinct non-null values
        completeness – percentage of non-null values (0–100)
        uniqueness   – percentage of distinct values relative to row count (0–100)
        standard     – the standard ID mapped to this column (or None)
        standard_name – the standard's human-readable name (or None)
        validity_pct – percentage of non-null values passing the standard (or None if unmapped)
        sample       – first 3 non-null values as strings (truncated to 50 chars each)
    """
    stats = []   # Accumulate one dict per column
    n = len(df)  # Row count used in percentage calculations

    for col in df.columns:
        series = df[col]  # The full column Series (with nulls)

        null_count   = int(series.isnull().sum())          # Count of null cells in this column
        unique_count = int(series.nunique(dropna=True))    # Count of distinct non-null values
        completeness = round((n - null_count) / n * 100, 1) if n else 0.0   # % non-null
        uniqueness   = round(unique_count / n * 100, 1)    if n else 0.0    # % distinct vs total rows

        std_id      = column_standards.get(col)  # Standard ID mapped to this column (or None)
        validity_pct = None                       # Only computed if column has a mapped standard

        if std_id:
            non_null = series.dropna()  # Work only on non-null values
            if len(non_null):
                # Count values passing the standard check
                valid_count  = sum(check_value(v, std_id) for v in non_null.astype(str))
                validity_pct = round(valid_count / len(non_null) * 100, 1)  # Percentage valid
            else:
                validity_pct = 0.0  # All null → 0% valid

        # Take the first 3 non-null values as sample display values
        sample = series.dropna().head(3).tolist()   # Up to 3 non-null values as Python objects
        sample = [str(v)[:50] for v in sample]      # Cast to string and truncate at 50 characters

        stats.append({
            "column":        col,
            "dtype":         str(series.dtype),     # e.g. "object", "int64", "float64"
            "null_count":    null_count,
            "unique_count":  unique_count,
            "completeness":  completeness,           # % non-null
            "uniqueness":    uniqueness,             # % distinct values
            "standard":      std_id,                # Standard ID or None
            "standard_name": DATA_STANDARDS.get(std_id, {}).get("name") if std_id else None,
            "validity_pct":  validity_pct,          # % valid vs standard, or None
            "sample":        sample,                # First 3 values as strings
        })

    return stats  # Return the list of column stat dicts


# =============================================================================
# Helper functions
# =============================================================================

def _rate_to_score(rate: float, target: float) -> float:
    """
    Convert an observed rate (0.0–1.0) to a 0–100 score using a linear scale.

    Formula: score = min(rate / target, 1.0) * 100

    Behaviour:
        rate >= target → score = 100  (full marks — at or above the target)
        rate = 0.0     → score = 0    (worst possible)
        0 < rate < target → score scales linearly between 0 and 100

    Edge case: if target is 0 or negative (misconfiguration), return 100 to
    avoid division by zero.
    """
    if target <= 0:
        return 100.0  # Guard against zero or negative target (config error)

    # min(..., 1.0) caps the ratio at 1.0 so scores above target don't exceed 100
    score = min(rate / target, 1.0) * 100.0

    return round(score, 2)


def _empty_result(col_count: int) -> Dict[str, Any]:
    """
    Return a zeroed-out profiling result dict for an empty DataFrame.

    Called when len(df) == 0 to avoid division-by-zero errors in all the
    dimension checkers.  Each dimension gets a score of 0 and a generic
    "Empty dataset" description.
    """
    return {
        # Build a dict of dimension_key → minimal result dict using a comprehension
        "dimensions":     {d: {"score": 0, "description": "Empty dataset"} for d in PROFILING_DIMENSION_WEIGHTS},
        "overall_score":  0.0,        # Weighted score of all zeros is zero
        "column_stats":   [],         # No columns to report
        "row_count":      0,          # Confirmed empty
        "col_count":      col_count,  # Preserve column count (may still be non-zero)
        "duplicate_rows": 0,          # No rows → no duplicates
        "gx_used":        False,      # GX was not run on an empty DataFrame
    }
