"""Tests for processed Parquet loader helpers."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from energy_ingestion.loaders.processed_loader import (
    ProcessedLoaderError,
    load_dataframe_parquet,
    save_dataframe_parquet,
)


def test_save_and_load_dataframe_parquet(tmp_path) -> None:
    extracted_at = datetime(2026, 6, 1, 12, 30, tzinfo=UTC)
    df = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp("2026-06-01T00:00:00Z"),
                "metric": "consumption_short_term",
                "type": "REALISED",
                "value": 40685.0,
            },
            {
                "timestamp": pd.Timestamp("2026-06-01T00:15:00Z"),
                "metric": "consumption_short_term",
                "type": "REALISED",
                "value": 40765.0,
            },
        ]
    )

    path = save_dataframe_parquet(
        df,
        dataset="consumption",
        processed_data_dir=tmp_path / "processed",
        extracted_at=extracted_at,
    )
    loaded_df = load_dataframe_parquet(path)

    assert path.name == "20260601T123000000000Z.parquet"
    assert "dataset" not in loaded_df.columns
    assert len(loaded_df) == 2
    assert loaded_df["value"].tolist() == [40685.0, 40765.0]
    assert pd.api.types.is_datetime64_any_dtype(loaded_df["timestamp"])


def test_save_dataframe_parquet_refuses_empty_dataframe(tmp_path) -> None:
    with pytest.raises(ProcessedLoaderError):
        save_dataframe_parquet(
            pd.DataFrame(),
            dataset="consumption",
            processed_data_dir=tmp_path / "processed",
        )
