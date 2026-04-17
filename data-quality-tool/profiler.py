# =============================================================================
# DATA QUALITY ASSESSMENT TOOL – PROFILING ENGINE
# =============================================================================
from __future__ import annotations

import re
import warnings
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

import numpy as np
import pandas as pd

from config import (
    COMPLETENESS_TARGET, UNIQUENESS_TARGET, VALIDITY_TARGET,
    CONSISTENCY_TARGET, TIMELINESS_DAYS, TIMELINESS_TARGET,
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
) -> Dict[str, Any]:
    total_rows, total_cols = len(df), len(df.columns)

    if total_rows == 0:
        return _empty_result(total_cols)

    completeness = _check_completeness(df)
    uniqueness   = _check_uniqueness(df)
    validity     = _check_validity(df, column_standards)
    consistency  = _check_consistency(df)
    timeliness   = _check_timeliness(df, column_standards)

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
        "consistency":  consistency,
        "timeliness":   timeliness,
    }

    overall = sum(
        dimensions[dim]["score"] * PROFILING_DIMENSION_WEIGHTS[dim]
        for dim in dimensions
    )

    column_stats = _build_column_stats(df, column_standards)

    return {
        "dimensions":     dimensions,
        "overall_score":  round(overall, 2),
        "column_stats":   column_stats,
        "row_count":      total_rows,
        "col_count":      total_cols,
        "duplicate_rows": int(df.duplicated().sum()),
        "gx_used":        gx_used,
    }


def _check_completeness(df: pd.DataFrame) -> Dict[str, Any]:
    total_cells = len(df) * len(df.columns)
    null_counts  = df.isnull().sum()
    total_nulls  = int(null_counts.sum())
    completeness_rate = (total_cells - total_nulls) / total_cells if total_cells else 0.0

    col_rates = {
        col: round((len(df) - int(null_counts[col])) / len(df) * 100, 1)
        for col in df.columns
    }

    score = _rate_to_score(completeness_rate, COMPLETENESS_TARGET)

    return {
        "score":       round(score, 2),
        "rate":        round(completeness_rate * 100, 2),
        "total_nulls": total_nulls,
        "column_rates": col_rates,
        "description": f"{completeness_rate*100:.1f}% of all cells are populated",
    }


def _check_uniqueness(df: pd.DataFrame) -> Dict[str, Any]:
    n = len(df)
    dup_count = int(df.duplicated().sum())
    unique_row_rate = (n - dup_count) / n if n else 0.0

    col_unique = {
        col: round(df[col].nunique(dropna=True) / n * 100, 1)
        for col in df.columns
    }

    score = _rate_to_score(unique_row_rate, UNIQUENESS_TARGET)

    return {
        "score":             round(score, 2),
        "unique_row_rate":   round(unique_row_rate * 100, 2),
        "duplicate_rows":    dup_count,
        "column_unique_pct": col_unique,
        "description":       f"{dup_count} exact duplicate row(s) found "
                             f"({(1-unique_row_rate)*100:.1f}% duplication rate)",
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
        valid_pct = valid_count / len(non_null) * 100
        col_rates[col] = {
            "standard":      std_id,
            "standard_name": DATA_STANDARDS.get(std_id, {}).get("name", std_id),
            "valid_pct":     round(valid_pct, 1),
            "invalid_count": len(non_null) - valid_count,
            "total_checked": len(non_null),
        }

    avg_valid = sum(v["valid_pct"] for v in col_rates.values()) / len(col_rates) if col_rates else 70.0
    score = _rate_to_score(avg_valid / 100, VALIDITY_TARGET)
    unmapped = [c for c in df.columns if c not in column_standards]

    return {
        "score":         round(score, 2),
        "rate":          round(avg_valid, 2),
        "column_rates":  col_rates,
        "unmapped_cols": unmapped,
        "description":   f"{avg_valid:.1f}% of mapped values conform to their data standard",
    }


def _check_consistency(df: pd.DataFrame) -> Dict[str, Any]:
    col_scores = {}
    for col in df.columns:
        series = df[col].dropna().astype(str)
        if len(series) == 0:
            col_scores[col] = 100.0
            continue

        numeric_count = pd.to_numeric(series, errors="coerce").notna().sum()
        if numeric_count / len(series) >= 0.5:
            col_scores[col] = round(numeric_count / len(series) * 100, 1)
            continue

        # infer_datetime_format removed in pandas 2.x
        date_count = pd.to_datetime(series, errors="coerce").notna().sum()
        if date_count / len(series) >= 0.5:
            col_scores[col] = round(date_count / len(series) * 100, 1)
            continue

        upper_count = sum(1 for v in series if v == v.upper() and not v.isdigit())
        lower_count = sum(1 for v in series if v == v.lower() and not v.isdigit())
        cap_count   = sum(1 for v in series if v.istitle())
        dominant    = max(upper_count, lower_count, cap_count)
        case_consistency = dominant / len(series) if len(series) else 1.0

        mixed_penalty = 20.0 if 0.05 < (numeric_count / len(series)) < 0.95 else 0.0
        col_scores[col] = max(0.0, round(min(case_consistency * 100, 100.0) - mixed_penalty, 1))

    avg = sum(col_scores.values()) / len(col_scores) if col_scores else 100.0
    score = _rate_to_score(avg / 100, CONSISTENCY_TARGET)

    return {
        "score":           round(score, 2),
        "avg_consistency": round(avg, 2),
        "column_scores":   col_scores,
        "description":     f"Average intra-column type/format consistency: {avg:.1f}%",
    }


def _check_timeliness(df: pd.DataFrame, column_standards: Dict[str, str]) -> Dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=TIMELINESS_DAYS)
    date_cols_checked = {}

    date_standard_ids = {sid for sid, meta in DATA_STANDARDS.items() if meta.get("is_date")}
    mapped_date_cols = {col for col, sid in column_standards.items() if sid in date_standard_ids}

    if not mapped_date_cols:
        for col in df.columns:
            if str(df[col].dtype).startswith("datetime"):
                mapped_date_cols.add(col)
            elif df[col].dtype == object:
                try:
                    sample = df[col].dropna().head(50).astype(str)
                    parsed = pd.to_datetime(sample, errors="coerce")
                    if parsed.notna().sum() / max(len(sample), 1) > 0.7:
                        mapped_date_cols.add(col)
                except Exception:
                    pass

    if not mapped_date_cols:
        return {
            "score":        75.0,
            "checked_cols": {},
            "description":  "No date columns detected – timeliness not assessed",
        }

    for col in mapped_date_cols:
        if col not in df.columns:
            continue
        try:
            raw = df[col].dropna()
            parsed = pd.to_datetime(raw, errors="coerce", utc=True)
            valid_dates = parsed.dropna()
            if len(valid_dates) == 0:
                continue
            timely = (valid_dates >= pd.Timestamp(cutoff)).sum()
            timely_pct = timely / len(valid_dates) * 100
            date_cols_checked[col] = {
                "timely_pct":   round(float(timely_pct), 1),
                "oldest_value": str(valid_dates.min().date()),
                "newest_value": str(valid_dates.max().date()),
            }
        except Exception:
            pass

    if date_cols_checked:
        avg_timely = sum(v["timely_pct"] for v in date_cols_checked.values()) / len(date_cols_checked)
        score = _rate_to_score(avg_timely / 100, TIMELINESS_TARGET)
    else:
        avg_timely, score = 75.0, 75.0

    return {
        "score":        round(score, 2),
        "checked_cols": date_cols_checked,
        "description":  f"{avg_timely:.1f}% of date values are within the last {TIMELINESS_DAYS} days",
    }


def _run_gx_expectations(df: pd.DataFrame, column_standards: Dict[str, str]) -> Dict[str, Any]:
    context = gx.get_context(mode="ephemeral")
    ds = context.data_sources.add_pandas("dq_source")
    asset = ds.add_dataframe_asset("dq_asset")
    batch_def = asset.add_batch_definition_whole_dataframe("dq_batch")
    suite = context.suites.add(gx.ExpectationSuite(name="dq_suite"))

    for col in df.columns:
        suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column=col))

    for col, std_id in column_standards.items():
        if col not in df.columns:
            continue
        std = DATA_STANDARDS.get(std_id, {})
        pattern = std.get("pattern")
        if pattern and not std.get("custom_check"):
            flags = std.get("flags", 0)
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


def _build_column_stats(df: pd.DataFrame, column_standards: Dict[str, str]) -> List[Dict[str, Any]]:
    stats = []
    n = len(df)
    for col in df.columns:
        series = df[col]
        null_count   = int(series.isnull().sum())
        unique_count = int(series.nunique(dropna=True))
        completeness = round((n - null_count) / n * 100, 1) if n else 0.0
        uniqueness   = round(unique_count / n * 100, 1) if n else 0.0

        std_id = column_standards.get(col)
        validity_pct = None
        if std_id:
            non_null = series.dropna()
            if len(non_null):
                valid_count = sum(check_value(v, std_id) for v in non_null.astype(str))
                validity_pct = round(valid_count / len(non_null) * 100, 1)
            else:
                validity_pct = 0.0

        sample = [str(v)[:50] for v in series.dropna().head(3).tolist()]

        stats.append({
            "column":        col,
            "dtype":         str(series.dtype),
            "null_count":    null_count,
            "unique_count":  unique_count,
            "completeness":  completeness,
            "uniqueness":    uniqueness,
            "standard":      std_id,
            "standard_name": DATA_STANDARDS.get(std_id, {}).get("name") if std_id else None,
            "validity_pct":  validity_pct,
            "sample":        sample,
        })
    return stats


def _rate_to_score(rate: float, target: float) -> float:
    if target <= 0:
        return 100.0
    return round(min(rate / target, 1.0) * 100.0, 2)


def _empty_result(col_count: int) -> Dict[str, Any]:
    return {
        "dimensions":     {d: {"score": 0, "description": "Empty dataset"} for d in PROFILING_DIMENSION_WEIGHTS},
        "overall_score":  0.0,
        "column_stats":   [],
        "row_count":      0,
        "col_count":      col_count,
        "duplicate_rows": 0,
        "gx_used":        False,
    }
