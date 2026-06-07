"""Ingest Open-Meteo hourly weather data into raw, processed and PostgreSQL."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parents[2]))

from energy_ingestion.clients.weather_client import WeatherClient
from energy_ingestion.loaders.postgres_loader import insert_energy_measurements
from energy_ingestion.loaders.processed_loader import save_dataframe_parquet
from energy_ingestion.logging import configure_logging
from energy_ingestion.transforms.weather_transform import (
    average_weather_locations,
    transform_weather,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_HOURLY_VARIABLES = (
    "temperature_2m",
    "shortwave_radiation",
    "wind_speed_100m",
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WeatherLocation:
    name: str
    latitude: float
    longitude: float


# RTE consumption is national in this project, so these points act as a simple
# geographic proxy for France's main climate areas instead of relying on Paris.
DEFAULT_WEATHER_LOCATIONS = (
    WeatherLocation("Lille", 50.6292, 3.0573),
    WeatherLocation("Paris", 48.8566, 2.3522),
    WeatherLocation("Strasbourg", 48.5734, 7.7521),
    WeatherLocation("Lyon", 45.7640, 4.8357),
    WeatherLocation("Marseille", 43.2965, 5.3698),
    WeatherLocation("Toulouse", 43.6047, 1.4442),
    WeatherLocation("Bordeaux", 44.8378, -0.5792),
    WeatherLocation("Nantes", 47.2184, -1.5536),
    WeatherLocation("Brest", 48.3904, -4.4861),
)


def main() -> None:
    configure_logging()
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args()

    logger.info(
        "weather_ingestion_started date=%s location_count=%s hourly=%s",
        args.date,
        len(args.locations),
        args.hourly,
    )
    location_dataframes = []
    raw_paths = []
    with WeatherClient() as client:
        for location in args.locations:
            logger.info(
                "weather_location_fetching date=%s location=%s latitude=%s longitude=%s",
                args.date,
                location.name,
                location.latitude,
                location.longitude,
            )
            response = client.get_hourly_weather(
                latitude=location.latitude,
                longitude=location.longitude,
                start_date=args.date.isoformat(),
                end_date=args.date.isoformat(),
                hourly=tuple(args.hourly),
                timezone=args.timezone,
            )
            raw_paths.append(response.raw_path)
            location_dataframes.append(
                transform_weather(response.json(), location_name=location.name)
            )

    # Keep local observations and append a France row averaged across locations.
    average_df = average_weather_locations(location_dataframes, average_zone=args.average_zone)
    df = pd.concat([*location_dataframes, average_df], ignore_index=True)
    parquet_path = save_dataframe_parquet(df, dataset="weather")
    inserted_count = insert_energy_measurements(df)

    logger.info(
        "weather_ingestion_finished rows=%s inserted_count=%s raw_count=%s parquet_path=%s",
        len(df),
        inserted_count,
        len(raw_paths),
        parquet_path,
    )
    print("OK - fichiers meteo sauvegardes :", len(raw_paths))
    print("Parquet :", parquet_path)
    print("Lignes inserees :", inserted_count)


def parse_args() -> argparse.Namespace:
    default_date = date.today() - timedelta(days=1)
    parser = argparse.ArgumentParser(description="Ingest Open-Meteo hourly weather data.")
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        default=default_date,
        help="Date to ingest in YYYY-MM-DD format. Defaults to yesterday.",
    )
    parser.add_argument(
        "--locations",
        nargs="+",
        default=None,
        help=(
            "Locations as Name:latitude:longitude. "
            "Defaults to WEATHER_LOCATIONS or strategic French cities."
        ),
    )
    parser.add_argument(
        "--average-zone",
        default=os.getenv("WEATHER_AVERAGE_ZONE", "France"),
        help="Zone label used for the averaged weather rows.",
    )
    parser.add_argument(
        "--timezone",
        default=os.getenv("WEATHER_TIMEZONE", "Europe/Paris"),
        help="Timezone requested from Open-Meteo.",
    )
    parser.add_argument(
        "--hourly",
        nargs="+",
        default=list(_hourly_variables_from_env()),
        help="Open-Meteo hourly variables to ingest.",
    )
    args = parser.parse_args()
    args.locations = _parse_locations(args.locations)
    return args


def _parse_locations(values: list[str] | None) -> list[WeatherLocation]:
    raw_locations = values or _locations_from_env()
    if raw_locations is None:
        return list(DEFAULT_WEATHER_LOCATIONS)

    locations = []
    for raw_location in raw_locations:
        try:
            name, latitude, longitude = raw_location.split(":", maxsplit=2)
            locations.append(WeatherLocation(name, float(latitude), float(longitude)))
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                f"Invalid location '{raw_location}'. Expected Name:latitude:longitude."
            ) from exc
    return locations


def _locations_from_env() -> list[str] | None:
    value = os.getenv("WEATHER_LOCATIONS", "").strip()
    if not value:
        return None
    return [location.strip() for location in value.split(",") if location.strip()]


def _hourly_variables_from_env() -> tuple[str, ...]:
    value = os.getenv("WEATHER_HOURLY_VARIABLES", "").strip()
    if not value:
        return DEFAULT_HOURLY_VARIABLES
    variables = tuple(variable.strip() for variable in value.split(",") if variable.strip())
    return variables or DEFAULT_HOURLY_VARIABLES


if __name__ == "__main__":
    main()
