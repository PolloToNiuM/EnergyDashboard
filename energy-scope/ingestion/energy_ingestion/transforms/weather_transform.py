"""Transform Open-Meteo raw weather data into normalized dataframes."""

from __future__ import annotations

import logging
from datetime import timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from energy_ingestion.transforms.common import remove_duplicates


WEATHER_HOURLY_METRIC = "weather_hourly"
DEFAULT_WEATHER_SOURCE = "Open-Meteo"

logger = logging.getLogger(__name__)


def transform_weather(raw_data: dict, *, location_name: str = "Paris") -> pd.DataFrame:
    """Normalize Open-Meteo hourly data for storage in energy_measurements."""
    hourly = raw_data.get("hourly", {})
    timestamps = hourly.get("time", [])
    if not timestamps:
        logger.warning("weather_transform_empty reason=no_hourly_time")
        return _empty_weather_dataframe()

    timezone_name = raw_data.get("timezone", "UTC")
    timestamp_series = _parse_weather_timestamps(timestamps, timezone_name)
    hourly_units = raw_data.get("hourly_units", {})
    rows: list[dict[str, object]] = []

    for variable, values in hourly.items():
        if variable == "time":
            continue

        unit = _normalize_weather_unit(hourly_units.get(variable, "unknown"))
        for timestamp, value in zip(timestamp_series, values, strict=False):
            if value is None or pd.isna(value):
                continue

            rows.append(
                {
                    "timestamp": timestamp,
                    "end_date": timestamp + timedelta(hours=1),
                    "updated_date": None,
                    "source": DEFAULT_WEATHER_SOURCE,
                    "metric": WEATHER_HOURLY_METRIC,
                    "measurement_type": variable,
                    "production_type": "",
                    "value": float(value),
                    "unit": unit,
                    "zone": location_name,
                    "granularity": "1h",
                }
            )

    df = pd.DataFrame(rows)
    if df.empty:
        logger.warning("weather_transform_empty reason=no_values")
        return _empty_weather_dataframe()

    df = remove_duplicates(df, subset=["timestamp", "measurement_type", "zone"])
    logger.info(
        "weather_transformed rows=%s variables=%s location=%s",
        len(df),
        sorted(df["measurement_type"].unique().tolist()),
        location_name,
    )
    return df[
        [
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
    ]


def average_weather_locations(
    dataframes: list[pd.DataFrame],
    *,
    average_zone: str = "France",
) -> pd.DataFrame:
    """Average equivalent weather variables across several locations.

    The input dataframes keep each city as its own zone. This function adds a
    national proxy by averaging values that share the same timestamp and weather
    variable, which is what we need to compare against national RTE consumption.
    """
    non_empty_dataframes = [df for df in dataframes if not df.empty]
    if not non_empty_dataframes:
        logger.warning("weather_average_empty reason=no_location_data")
        return _empty_weather_dataframe()

    combined = pd.concat(non_empty_dataframes, ignore_index=True)
    group_columns = [
        "timestamp",
        "end_date",
        "source",
        "metric",
        "measurement_type",
        "production_type",
        "unit",
        "granularity",
    ]

    averaged = (
        combined.groupby(group_columns, dropna=False, as_index=False)["value"]
        .mean()
        .assign(updated_date=None, zone=average_zone)
    )
    averaged = averaged[
        [
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
    ]
    logger.info(
        "weather_locations_averaged rows=%s location_count=%s average_zone=%s",
        len(averaged),
        len(non_empty_dataframes),
        average_zone,
    )
    return averaged


def _parse_weather_timestamps(timestamps: list[str], timezone_name: str) -> pd.Series:
    parsed = pd.to_datetime(pd.Series(timestamps))
    if parsed.dt.tz is None:
        parsed = parsed.dt.tz_localize(ZoneInfo(timezone_name)).dt.tz_convert("UTC")
    else:
        parsed = parsed.dt.tz_convert("UTC")
    return parsed


def _normalize_weather_unit(unit: str) -> str:
    if unit == "°C":
        return "C"
    return unit.strip() or "unknown"


def _empty_weather_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
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
    )
