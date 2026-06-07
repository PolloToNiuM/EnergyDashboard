"""Reusable data quality checks for normalized measurement dataframes."""

from __future__ import annotations

import logging
from typing import Iterable

import pandas as pd


logger = logging.getLogger(__name__)

REQUIRED_NON_NULL_COLUMNS = ("timestamp", "value", "source", "metric")
OPTIONAL_KEY_COLUMNS = ("measurement_type", "production_type")
MEASUREMENT_NATURAL_KEY = (
    "timestamp",
    "source",
    "metric",
    "measurement_type",
    "production_type",
    "zone",
)


class QualityCheckError(ValueError):
    """Raised when a dataframe does not satisfy ingestion quality rules."""


def validate_measurements_dataframe(
    df: pd.DataFrame,
    *,
    duplicate_subset: Iterable[str] = MEASUREMENT_NATURAL_KEY,
) -> pd.DataFrame:
    """Validate measurement rows before persisting them.

    Rules intentionally stay simple and strict:
    timestamp, value, source and metric must be present and non-null, values
    must be numeric and positive or zero, and the natural measurement key must
    not contain duplicates.
    """
    normalized = _normalize_measurement_columns(df)
    errors: list[str] = []

    for column in REQUIRED_NON_NULL_COLUMNS:
        if column not in normalized.columns:
            errors.append(f"missing required column '{column}'")
            continue

        null_count = int(normalized[column].isna().sum())
        if null_count:
            errors.append(f"column '{column}' contains {null_count} null values")

        if column in {"source", "metric"}:
            blank_count = _blank_string_count(normalized[column])
            if blank_count:
                errors.append(f"column '{column}' contains {blank_count} blank values")

    if "value" in normalized.columns:
        numeric_values = pd.to_numeric(normalized["value"], errors="coerce")
        non_numeric_count = int(numeric_values.isna().sum() - normalized["value"].isna().sum())
        if non_numeric_count:
            errors.append(f"column 'value' contains {non_numeric_count} non numeric values")

        negative_count = int((numeric_values < 0).sum())
        if negative_count:
            errors.append(f"column 'value' contains {negative_count} negative values")

    duplicate_columns = tuple(duplicate_subset)
    missing_duplicate_columns = [
        column for column in duplicate_columns if column not in normalized.columns
    ]
    if missing_duplicate_columns:
        errors.append(
            "duplicate check missing columns: "
            + ", ".join(f"'{column}'" for column in missing_duplicate_columns)
        )
    else:
        duplicate_count = int(normalized.duplicated(subset=list(duplicate_columns)).sum())
        if duplicate_count:
            errors.append(f"natural key contains {duplicate_count} duplicate rows")

    if errors:
        message = "; ".join(errors)
        logger.error("quality_checks_failed row_count=%s errors=%s", len(normalized), message)
        raise QualityCheckError(message)

    logger.info("quality_checks_passed row_count=%s", len(normalized))
    return normalized


def _normalize_measurement_columns(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    if "type" in normalized.columns and "measurement_type" not in normalized.columns:
        normalized = normalized.rename(columns={"type": "measurement_type"})

    for column in OPTIONAL_KEY_COLUMNS:
        if column not in normalized.columns:
            normalized[column] = ""
        else:
            normalized[column] = normalized[column].fillna("")

    return normalized


def _blank_string_count(series: pd.Series) -> int:
    return int(series.astype("string").str.strip().eq("").fillna(False).sum())
