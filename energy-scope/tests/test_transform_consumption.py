"""Tests for RTE consumption raw data transformation."""

from __future__ import annotations

import pandas as pd

from energy_ingestion.transforms.consumption_transform import transform_consumption


def test_transform_consumption_returns_expected_dataframe() -> None:
    raw_data = {
        "short_term": [
            {
                "type": "REALISED",
                "values": [
                    {
                        "start_date": "2026-06-01T00:00:00+02:00",
                        "end_date": "2026-06-01T00:15:00+02:00",
                        "updated_date": "2026-06-01T00:20:00+02:00",
                        "value": 40685,
                    },
                    {
                        "start_date": "2026-06-01T00:00:00+02:00",
                        "end_date": "2026-06-01T00:15:00+02:00",
                        "updated_date": "2026-06-01T00:20:00+02:00",
                        "value": 40685,
                    },
                ],
            },
            {
                "type": "ID",
                "values": [
                    {
                        "start_date": "2026-06-01T00:15:00+02:00",
                        "end_date": "2026-06-01T00:30:00+02:00",
                        "updated_date": "2026-06-01T00:35:00+02:00",
                        "value": 40100,
                    },
                ],
            },
        ]
    }

    df = transform_consumption(raw_data)

    assert list(df.columns) == [
        "timestamp",
        "end_date",
        "updated_date",
        "source",
        "metric",
        "type",
        "value",
        "unit",
        "zone",
        "granularity",
    ]
    assert len(df) == 2
    assert not df.duplicated(subset=["timestamp", "type"]).any()
    assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
    assert str(df["timestamp"].dt.tz) == "UTC"
    assert df["metric"].unique().tolist() == ["consumption_short_term"]
    assert df["source"].unique().tolist() == ["RTE"]
    assert df["unit"].unique().tolist() == ["MW"]
    assert df["zone"].unique().tolist() == ["France"]
    assert df["granularity"].unique().tolist() == ["15min"]
