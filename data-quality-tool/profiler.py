# =============================================================================
# DATA QUALITY ASSESSMENT TOOL – PROFILING ENGINE
# =============================================================================
from __future__ import annotations

import re
import warnings
from typing import Dict, List, Any

import numpy as np
import pandas as pd

from config import (
    COMPLETENESS_TARGET, UNIQUENESS_TARGET, VALIDITY_TARGET,
    DATA_USE_TYPE_WEIGHTS, DATA_USE_TYPE_LABELS, DEFAULT_DATA_USE_TYPE,
    PROFILING_DIMENSION_WEIGHTS,
)
from standards import DATA_STANDARDS, check_value

warnings.filterwarnings("ignore")

_GX_AVAILABLE = False
try:
    import great_expectations as gx
    _GX_AVAILABLE = True
except ImportError:
    pass


def profile_dataframe(
    df: pd.DataFrame,
    column_standards: Dict[str, str],
    column_flags: Dict[str, Dict[str, bool]] = None,
    data_use_type: str = None,
) -> Dict[str, Any]:
    """
    Scores completeness, uniqueness and validity against columns the user
    explicitly selected.  Weights are determined by the chosen data use type.
    """
    if column_flags is None:
        column_flags = {}
    if data_use_type is None:
        data_use_type = DEFAULT_DATA_USE_TYPE

    weights = DATA_USE_TYPE_WEIGHTS.get(data_use_type, PROFILING_DIMENSION_WEIGHTS)

    total_rows, total_cols = len(df), len(df.columns)
    if total_rows == 0:
        return _empty_result(total_cols, data_use_type, weights)

    mandatory_cols = [c for c, f in column_flags.items() if f.get("mandatory") and c in df.columns]
    unique_cols    = [c for c, f in column_flags.items() if f.get("unique")    and c in df.columns]

    comp_scope   = mandatory_cols if column_flags else None
    unique_scope = unique_cols    if unique_cols  else None

    completeness = _check_completeness(df, comp_scope)
    uniqueness   = _check_uniqueness(df, unique_scope)
    validity     = _check_validity(df, column_standards)

    gx_used = False
    if _GX_AVAILABLE:
        try:
            gx_enrichments = _run_gx_expectations(df, column_standards)
            if gx_enrichments.get("completeness_override") is not None:
                completeness["score"] = gx_enrichments["completeness_override"]
            gx_used = True
        except Exception:
            pass

    dimensions = {
        "completeness": completeness,
        "uniqueness":   uniqueness,
        "validity":     validity,
    }

    overall = sum(
        dimensions[dim]["score"] * weights.get(dim, 0)
        for dim in dimensions
    )

    column_stats = _build_column_stats(
        df, column_standards,
        mandatory_cols=mandatory_cols if column_flags else None,
        unique_cols=unique_cols        if unique_cols  else None,
        flags_in_use=bool(column_flags),
    )

    return {
        "dimensions":     dimensions,
        "overall_score":  round(overall, 2),
        "column_stats":   column_stats,
        "row_count":      total_rows,
        "col_count":      total_cols,
        "duplicate_rows": int(df.duplicated().sum()),
        "gx_used":        gx_used,
        "data_use_type":  data_use_type,
        "type_label":     DATA_USE_TYPE_LABELS.get(data_use_type, data_use_type),
        "weights_used":   weights,
    }


def _check_completeness(df: pd.DataFrame, mandatory_cols=None) -> Dict[str, Any]:
    if mandatory_cols is not None and len(mandatory_cols) == 0:
        return {
            "score":        70.0,
            "rate":         None,
            "total_nulls":  None,
            "column_rates": {},
            "description":  "No mandatory columns flagged – completeness not assessed",
        }

    check_cols  = mandatory_cols if mandatory_cols is not None else list(df.columns)
    subset      = df[check_cols]
    total_cells = len(subset) * len(subset.columns)
    null_counts = subset.isnull().sum()
    total_nulls = int(null_counts.sum())
    rate        = (total_cells - total_nulls) / total_cells if total_cells else 0.0
    col_rates   = {
        col: round((len(df) - int(null_counts[col])) / len(df) * 100, 1)
        for col in check_cols
    }
    prefix = "Mandatory columns: " if mandatory_cols is not None else ""
    return {
        "score":        round(_rate_to_score(rate, COMPLETENESS_TARGET), 2),
        "rate":         round(rate * 100, 2),
        "total_nulls":  total_nulls,
        "column_rates": col_rates,
        "description":  f"{prefix}{rate*100:.1f}% of cells are populated",
    }


def _check_uniqueness(df: pd.DataFrame, unique_cols=None) -> Dict[str, Any]:
    n = len(df)

    if unique_cols is None:
        dup_count       = int(df.duplicated().sum())
        unique_row_rate = (n - dup_count) / n if n else 0.0
        col_unique      = {col: round(df[col].nunique(dropna=True) / n * 100, 1) for col in df.columns}
        return {
            "score":             round(_rate_to_score(unique_row_rate, UNIQUENESS_TARGET), 2),
            "unique_row_rate":   round(unique_row_rate * 100, 2),
            "duplicate_rows":    dup_count,
            "column_unique_pct": col_unique,
            "description":       f"{dup_count} exact duplicate row(s) found "
                                 f"({(1-unique_row_rate)*100:.1f}% duplication rate)",
        }

    col_unique = {
        col: round(df[col].nunique(dropna=True) / n * 100, 1)
        for col in unique_cols
    }
    avg_unique = sum(col_unique.values()) / len(col_unique) if col_unique else 0.0
    return {
        "score":             round(_rate_to_score(avg_unique / 100, UNIQUENESS_TARGET), 2),
        "unique_row_rate":   None,
        "duplicate_rows":    None,
        "column_unique_pct": col_unique,
        "description":       f"Unique-flagged columns: {avg_unique:.1f}% average unique values",
    }


def _check_validity(df: pd.DataFrame, column_standards: Dict[str, str]) -> Dict[str, Any]:
    if not column_standards:
        return {
            "score":         70.0,
            "rate":          None,
            "column_rates":  {},
            "unmapped_cols": list(df.columns),
            "description":   "No columns mapped to standards – validity not assessed",
        }

    col_rates = {}
    for col, std_id in column_standards.items():
        if col not in df.columns:
            continue
        non_null = df[col].dropna()
        if len(non_null) == 0:
            col_rates[col] = {"standard": std_id, "valid_pct": 0.0, "invalid_count": 0}
            continue
        valid_count = sum(check_value(v, std_id) for v in non_null.astype(str).tolist())
        valid_pct   = valid_count / len(non_null) * 100
        col_rates[col] = {
            "standard":      std_id,
            "standard_name": DATA_STANDARDS.get(std_id, {}).get("name", std_id),
            "valid_pct":     round(valid_pct, 1),
            "invalid_count": len(non_null) - valid_count,
            "total_checked": len(non_null),
        }

    avg_valid = sum(v["valid_pct"] for v in col_rates.values()) / len(col_rates) if col_rates else 70.0
    unmapped  = [c for c in df.columns if c not in column_standards]
    return {
        "score":         round(_rate_to_score(avg_valid / 100, VALIDITY_TARGET), 2),
        "rate":          round(avg_valid, 2),
        "column_rates":  col_rates,
        "unmapped_cols": unmapped,
        "description":   f"{avg_valid:.1f}% of mapped values conform to their data standard",
    }


def _run_gx_expectations(df: pd.DataFrame, column_standards: Dict[str, str]) -> Dict[str, Any]:
    context   = gx.get_context(mode="ephemeral")
    ds        = context.data_sources.add_pandas("dq_source")
    asset     = ds.add_dataframe_asset("dq_asset")
    batch_def = asset.add_batch_definition_whole_dataframe("dq_batch")
    suite     = context.suites.add(gx.ExpectationSuite(name="dq_suite"))

    for col in df.columns:
        suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column=col))

    for col, std_id in column_standards.items():
        if col not in df.columns:
            continue
        std     = DATA_STANDARDS.get(std_id, {})
        pattern = std.get("pattern")
        if pattern and not std.get("custom_check"):
            flags    = std.get("flags", 0)
            gx_regex = f"(?i){pattern}" if flags & re.IGNORECASE else pattern
            try:
                suite.add_expectation(
                    gx.expectations.ExpectColumnValuesToMatchRegex(column=col, regex=gx_regex)
                )
            except Exception:
                pass

    val_def = context.validation_definitions.add(
        gx.ValidationDefinition(name="dq_validation", data=batch_def, suite=suite)
    )
    results = val_def.run(batch_parameters={"dataframe": df})

    completeness_scores = []
    for res in results.results:
        if res.expectation_config.type == "expect_column_values_to_not_be_null":
            unexpected_pct = res.result.get("unexpected_percent", 0) or 0
            completeness_scores.append(100 - unexpected_pct)

    override = round(sum(completeness_scores) / len(completeness_scores), 2) if completeness_scores else None
    return {"completeness_override": override}


def _build_column_stats(
    df: pd.DataFrame,
    column_standards: Dict[str, str],
    mandatory_cols=None,
    unique_cols=None,
    flags_in_use: bool = False,
) -> List[Dict[str, Any]]:
    stats         = []
    n             = len(df)
    mandatory_set = set(mandatory_cols or [])
    unique_set    = set(unique_cols    or [])

    for col in df.columns:
        series             = df[col]
        null_count         = int(series.isnull().sum())
        unique_count       = int(series.nunique(dropna=True))
        is_mandatory       = col in mandatory_set
        is_unique_expected = col in unique_set

        show_completeness = (not flags_in_use) or is_mandatory
        show_uniqueness   = (not flags_in_use) or is_unique_expected

        completeness = round((n - null_count) / n * 100, 1) if show_completeness and n else None
        uniqueness   = round(unique_count / n * 100, 1)     if show_uniqueness   and n else None

        std_id = column_standards.get(col)
        validity_pct = None
        if std_id:
            non_null = series.dropna()
            if len(non_null):
                valid_count  = sum(check_value(v, std_id) for v in non_null.astype(str))
                validity_pct = round(valid_count / len(non_null) * 100, 1)
            else:
                validity_pct = 0.0

        stats.append({
            "column":             col,
            "dtype":              str(series.dtype),
            "null_count":         null_count,
            "unique_count":       unique_count,
            "completeness":       completeness,
            "uniqueness":         uniqueness,
            "is_mandatory":       is_mandatory,
            "is_unique_expected": is_unique_expected,
            "standard":           std_id,
            "standard_name":      DATA_STANDARDS.get(std_id, {}).get("name") if std_id else None,
            "validity_pct":       validity_pct,
            "sample":             [str(v)[:50] for v in series.dropna().head(3).tolist()],
        })
    return stats


def _rate_to_score(rate: float, target: float) -> float:
    if target <= 0:
        return 100.0
    return round(min(rate / target, 1.0) * 100.0, 2)


def _empty_result(col_count: int, data_use_type: str, weights: dict) -> Dict[str, Any]:
    return {
        "dimensions":     {d: {"score": 0, "description": "Empty dataset"} for d in weights},
        "overall_score":  0.0,
        "column_stats":   [],
        "row_count":      0,
        "col_count":      col_count,
        "duplicate_rows": 0,
        "gx_used":        False,
        "data_use_type":  data_use_type,
        "type_label":     DATA_USE_TYPE_LABELS.get(data_use_type, data_use_type),
        "weights_used":   weights,
    }
