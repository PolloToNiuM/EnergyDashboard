"""Tests for ingestion data quality checks."""

from __future__ import annotations

import pandas as pd
import pytest

from energy_ingestion.quality.checks import (
    QualityCheckError,
    validate_measurements_dataframe,
)


def _valid_measurements() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp("2026-06-01T00:00:00Z"),
                "source": "RTE",
                "metric": "consumption_short_term",
                "measurement_type": "consumption",
                "production_type": "",
                "value": 42_000.0,
                "unit": "MW",
                "zone": "France",
                "granularity": "1h",
            },
            {
                "timestamp": pd.Timestamp("2026-06-01T01:00:00Z"),
                "source": "RTE",
                "metric": "consumption_short_term",
                "measurement_type": "consumption",
                "production_type": "",
                "value": 41_500.0,
                "unit": "MW",
                "zone": "France",
                "granularity": "1h",
            },
        ]
    )


def test_validate_measurements_dataframe_accepts_valid_rows() -> None:
    df = _valid_measurements()

    validated_df = validate_measurements_dataframe(df)

    assert len(validated_df) == 2
    assert validated_df.equals(df)


def test_validate_measurements_dataframe_renames_type_column() -> None:
    df = _valid_measurements().rename(columns={"measurement_type": "type"})

    validated_df = validate_measurements_dataframe(df)

    assert "measurement_type" in validated_df.columns
    assert "type" not in validated_df.columns


def test_validate_measurements_dataframe_rejects_null_required_values() -> None:
    df = _valid_measurements()
    df.loc[0, "timestamp"] = pd.NaT
    df.loc[1, "metric"] = None

    with pytest.raises(QualityCheckError, match="timestamp.*null.*metric.*null"):
        validate_measurements_dataframe(df)


def test_validate_measurements_dataframe_rejects_negative_values() -> None:
    df = _valid_measurements()
    df.loc[0, "value"] = -1

    with pytest.raises(QualityCheckError, match="negative values"):
        validate_measurements_dataframe(df)


def test_validate_measurements_dataframe_rejects_duplicate_natural_keys() -> None:
    df = pd.concat([_valid_measurements().iloc[[0]], _valid_measurements().iloc[[0]]])

    with pytest.raises(QualityCheckError, match="duplicate rows"):
        validate_measurements_dataframe(df)
