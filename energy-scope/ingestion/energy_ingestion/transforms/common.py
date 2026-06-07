"""Shared helpers for raw-to-dataframe transforms."""

from __future__ import annotations

import pandas as pd


def normalize_timestamps(
    df: pd.DataFrame,
    columns: tuple[str, ...] = ("timestamp", "end_date", "updated_date"),
) -> pd.DataFrame:
    """Convert timestamp columns to UTC datetimes when they exist."""
    df = df.copy()
    for column in columns:
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], utc=True)
    return df


def add_standard_columns(
    df: pd.DataFrame,
    *,
    source: str = "RTE",
    metric: str,
    unit: str = "MW",
    zone: str = "France",
    granularity: str | None = None,
) -> pd.DataFrame:
    """Add metadata columns shared by transformed energy dataframes."""
    df = df.copy()
    df["source"] = source
    df["metric"] = metric
    df["unit"] = normalize_unit(unit)
    df["zone"] = zone
    df["granularity"] = granularity if granularity is not None else infer_granularity(df)
    return df


def normalize_unit(unit: str) -> str:
    """Normalize unit labels used across transforms."""
    return unit.strip().upper()


def infer_granularity(
    df: pd.DataFrame,
    *,
    timestamp_column: str = "timestamp",
    group_column: str | None = None,
) -> str:
    """Infer the most common time step from a dataframe."""
    if timestamp_column not in df.columns or df.empty:
        return "unknown"

    data = df.sort_values(timestamp_column)
    if group_column is not None and group_column in data.columns:
        intervals = data.groupby(group_column)[timestamp_column].diff().dropna()
    else:
        intervals = data[timestamp_column].diff().dropna()

    if intervals.empty:
        return "unknown"

    minutes = int(intervals.mode().iloc[0].total_seconds() // 60)
    if minutes % 60 == 0:
        return f"{minutes // 60}h"
    return f"{minutes}min"


def remove_duplicates(
    df: pd.DataFrame,
    subset: list[str] | None = None,
) -> pd.DataFrame:
    """Remove duplicate rows while keeping the first observed value."""
    return df.drop_duplicates(subset=subset, keep="first").reset_index(drop=True)
