"""Service layer for measurements."""

import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.energy_measurement import EnergyMeasurement
from app.repositories.measurements import MeasurementRepository

PROJECT_ROOT = Path(__file__).resolve().parents[3]
INGESTION_ROOT = PROJECT_ROOT / "ingestion"

if str(INGESTION_ROOT) not in sys.path:
    sys.path.append(str(INGESTION_ROOT))

from energy_ingestion.clients.rte_client import RTEClient
from energy_ingestion.transforms.actual_generation_transform import (
    ACTUAL_GENERATION_ENDPOINT,
    transform_actual_generation,
)
from energy_ingestion.transforms.consumption_transform import (
    CONSUMPTION_ENDPOINT,
    transform_consumption,
)

ACTUAL_GENERATION_METRIC = "actual_generation_per_production_type"
CONSUMPTION_METRIC = "consumption_short_term"
MAX_INTERPOLATION_GAP = timedelta(hours=6)


@dataclass(frozen=True)
class InterpolatedMeasurement:
    id: int | None
    timestamp: datetime
    end_date: datetime | None
    updated_date: datetime | None
    source: str
    metric: str
    measurement_type: str
    production_type: str
    value: float
    unit: str
    zone: str
    granularity: str
    created_at: datetime | None
    is_interpolated: bool = True


class MeasurementService:
    """Coordinate measurement use cases."""

    def __init__(self, db: Session) -> None:
        self._repository = MeasurementRepository(db)

    def list_measurements(
        self,
        *,
        metric: str | None = None,
        source: str | None = None,
        zone: str | None = None,
        measurement_type: str | None = None,
        production_type: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EnergyMeasurement | InterpolatedMeasurement]:
        measurements = self._repository.list_measurements(
            metric=metric,
            source=source,
            zone=zone,
            measurement_type=measurement_type,
            production_type=production_type,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        )
        if (
            metric == ACTUAL_GENERATION_METRIC
            and start_date is not None
            and end_date is not None
            and offset == 0
            and production_type is None
        ):
            measurements = self._add_display_interpolations(
                measurements,
                start_date=start_date,
                end_date=end_date,
                source=source,
                zone=zone,
            )
        return measurements

    def sync_actual_generation_for_date(self, target_date: date) -> int:
        paris_tz = ZoneInfo("Europe/Paris")
        start_date = datetime.combine(target_date, time.min, tzinfo=paris_tz)
        end_date = start_date + timedelta(days=1)
        # Keep one hour around the day so the display layer can interpolate
        # clean 00:00 and 24:00 points when RTE has sparse boundary data.
        fetch_start_date = start_date - timedelta(hours=1)
        fetch_end_date = end_date + timedelta(hours=1)

        with RTEClient.from_env() as client:
            response = client.get_raw(
                ACTUAL_GENERATION_ENDPOINT,
                params={
                    "start_date": fetch_start_date.isoformat(),
                    "end_date": fetch_end_date.isoformat(),
                },
                dataset="actual_generation",
            )

        df = transform_actual_generation(response.json())
        return self._repository.insert_measurements(df)

    def sync_consumption_for_date(self, target_date: date) -> int:
        paris_tz = ZoneInfo("Europe/Paris")
        start_date = datetime.combine(target_date, time.min, tzinfo=paris_tz)
        end_date = start_date + timedelta(days=1)

        with RTEClient.from_env() as client:
            response = client.get_raw(
                CONSUMPTION_ENDPOINT,
                params={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
                dataset="consumption",
            )

        df = transform_consumption(response.json())
        return self._repository.insert_measurements(df)

    def _add_display_interpolations(
        self,
        measurements: list[EnergyMeasurement],
        *,
        start_date: datetime,
        end_date: datetime,
        source: str | None,
        zone: str | None,
    ) -> list[EnergyMeasurement | InterpolatedMeasurement]:
        existing_values = {
            (measurement.timestamp, measurement.production_type)
            for measurement in measurements
            if measurement.production_type
        }
        production_types = self._repository.list_production_types(
            metric=ACTUAL_GENERATION_METRIC,
            source=source,
            zone=zone,
        )
        additions: list[InterpolatedMeasurement] = []

        for timestamp in self._hourly_timestamps(start_date, end_date):
            for production_type in production_types:
                if (timestamp, production_type) in existing_values:
                    continue

                exact_measurement = self._repository.at_timestamp(
                    metric=ACTUAL_GENERATION_METRIC,
                    production_type=production_type,
                    timestamp=timestamp,
                    source=source,
                    zone=zone,
                )
                if exact_measurement is not None:
                    measurements.append(exact_measurement)
                    existing_values.add((timestamp, production_type))
                    continue

                previous_measurement = self._repository.latest_before(
                    metric=ACTUAL_GENERATION_METRIC,
                    production_type=production_type,
                    timestamp=timestamp,
                    source=source,
                    zone=zone,
                )
                next_measurement = self._repository.first_after(
                    metric=ACTUAL_GENERATION_METRIC,
                    production_type=production_type,
                    timestamp=timestamp,
                    source=source,
                    zone=zone,
                )
                if not self._can_interpolate(
                    previous_measurement,
                    next_measurement,
                    timestamp=timestamp,
                ):
                    continue

                additions.append(
                    self._interpolate_measurement(
                        previous_measurement,
                        next_measurement,
                        timestamp=timestamp,
                    )
                )

        if additions:
            interpolated_timestamps = {addition.timestamp for addition in additions}
            measurements = [
                measurement
                for measurement in measurements
                if not (
                    measurement.timestamp in interpolated_timestamps
                    and measurement.production_type == "TOTAL"
                )
            ]
            for timestamp in interpolated_timestamps:
                total_value = self._total_value_at_timestamp(
                    measurements,
                    additions,
                    timestamp,
                )
                if total_value is not None:
                    additions.append(
                        self._total_measurement(
                            timestamp=timestamp,
                            value=total_value,
                            source=source,
                            zone=zone,
                        )
                    )

        return sorted(
            [*measurements, *additions],
            key=lambda measurement: (measurement.timestamp, measurement.production_type),
        )

    @staticmethod
    def _hourly_timestamps(start_date: datetime, end_date: datetime) -> list[datetime]:
        timestamps: list[datetime] = []
        timestamp = start_date
        while timestamp <= end_date:
            timestamps.append(timestamp)
            timestamp += timedelta(hours=1)
        return timestamps

    @staticmethod
    def _can_interpolate(
        previous_measurement: EnergyMeasurement | None,
        next_measurement: EnergyMeasurement | None,
        *,
        timestamp: datetime,
    ) -> bool:
        if previous_measurement is None or next_measurement is None:
            return False
        if timestamp - previous_measurement.timestamp > MAX_INTERPOLATION_GAP:
            return False
        if next_measurement.timestamp - timestamp > MAX_INTERPOLATION_GAP:
            return False
        return previous_measurement.timestamp < timestamp < next_measurement.timestamp

    @staticmethod
    def _interpolate_measurement(
        previous_measurement: EnergyMeasurement,
        next_measurement: EnergyMeasurement,
        *,
        timestamp: datetime,
    ) -> InterpolatedMeasurement:
        total_seconds = (
            next_measurement.timestamp - previous_measurement.timestamp
        ).total_seconds()
        elapsed_seconds = (timestamp - previous_measurement.timestamp).total_seconds()
        ratio = elapsed_seconds / total_seconds
        value = previous_measurement.value + (
            next_measurement.value - previous_measurement.value
        ) * ratio

        return InterpolatedMeasurement(
            id=None,
            timestamp=timestamp,
            end_date=next_measurement.end_date,
            updated_date=None,
            source=next_measurement.source,
            metric=next_measurement.metric,
            measurement_type=next_measurement.measurement_type,
            production_type=next_measurement.production_type,
            value=float(value),
            unit=next_measurement.unit,
            zone=next_measurement.zone,
            granularity=next_measurement.granularity,
            created_at=None,
        )

    @staticmethod
    def _total_value_at_timestamp(
        measurements: list[EnergyMeasurement],
        additions: list[InterpolatedMeasurement],
        timestamp: datetime,
    ) -> float | None:
        values = [
            float(measurement.value)
            for measurement in measurements
            if measurement.timestamp == timestamp
            and measurement.production_type
            and measurement.production_type != "TOTAL"
        ]
        values.extend(
            addition.value
            for addition in additions
            if addition.timestamp == timestamp and addition.production_type != "TOTAL"
        )
        if not values:
            return None
        return sum(values)

    @staticmethod
    def _total_measurement(
        *,
        timestamp: datetime,
        value: float,
        source: str | None,
        zone: str | None,
    ) -> InterpolatedMeasurement:
        return InterpolatedMeasurement(
            id=None,
            timestamp=timestamp,
            end_date=timestamp + timedelta(hours=1),
            updated_date=None,
            source=source or "RTE",
            metric=ACTUAL_GENERATION_METRIC,
            measurement_type="",
            production_type="TOTAL",
            value=value,
            unit="MW",
            zone=zone or "France",
            granularity="1h",
            created_at=None,
        )
