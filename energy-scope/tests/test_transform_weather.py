"""Tests for Open-Meteo weather transformation."""

from __future__ import annotations

import pandas as pd

from energy_ingestion.transforms.weather_transform import (
    average_weather_locations,
    transform_weather,
)


def test_transform_weather_returns_normalized_hourly_dataframe() -> None:
    raw_data = {
        "timezone": "Europe/Paris",
        "hourly_units": {
            "time": "iso8601",
            "temperature_2m": "°C",
        },
        "hourly": {
            "time": [
                "2026-06-01T00:00",
                "2026-06-01T01:00",
                "2026-06-01T01:00",
            ],
            "temperature_2m": [18.4, 17.9, 17.9],
        },
    }

    df = transform_weather(raw_data, location_name="Paris")

    assert list(df.columns) == [
        "timestamp",
        "end_date",
        "updated_date",
        "source",
        "metric",
        "measurement_type",
        "production_type",
        "value",
        "unit",
        "zone",
        "granularity",
    ]
    assert len(df) == 2
    assert not df.duplicated(subset=["timestamp", "measurement_type", "zone"]).any()
    assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
    assert str(df["timestamp"].dt.tz) == "UTC"
    assert df["source"].unique().tolist() == ["Open-Meteo"]
    assert df["metric"].unique().tolist() == ["weather_hourly"]
    assert df["measurement_type"].unique().tolist() == ["temperature_2m"]
    assert df["unit"].unique().tolist() == ["C"]
    assert df["zone"].unique().tolist() == ["Paris"]
    assert df["granularity"].unique().tolist() == ["1h"]
    assert df.iloc[0]["timestamp"].isoformat() == "2026-05-31T22:00:00+00:00"


def test_average_weather_locations_returns_france_proxy() -> None:
    paris_df = transform_weather(
        {
            "timezone": "Europe/Paris",
            "hourly_units": {"time": "iso8601", "temperature_2m": "°C"},
            "hourly": {"time": ["2026-06-01T12:00"], "temperature_2m": [20.0]},
        },
        location_name="Paris",
    )
    lyon_df = transform_weather(
        {
            "timezone": "Europe/Paris",
            "hourly_units": {"time": "iso8601", "temperature_2m": "°C"},
            "hourly": {"time": ["2026-06-01T12:00"], "temperature_2m": [24.0]},
        },
        location_name="Lyon",
    )

    average_df = average_weather_locations([paris_df, lyon_df])

    assert len(average_df) == 1
    assert average_df.iloc[0]["zone"] == "France"
    assert average_df.iloc[0]["measurement_type"] == "temperature_2m"
    assert average_df.iloc[0]["value"] == 22.0
