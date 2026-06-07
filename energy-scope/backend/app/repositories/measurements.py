"""Repository for energy measurements."""

import logging
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import Select, distinct, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.energy_measurement import EnergyMeasurement


logger = logging.getLogger(__name__)


class MeasurementRepository:
    """Read energy measurements from the database."""

    def __init__(self, db: Session) -> None:
        self._db = db

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
    ) -> list[EnergyMeasurement]:
        query = select(EnergyMeasurement)
        query = self._apply_filters(
            query,
            metric=metric,
            source=source,
            zone=zone,
            measurement_type=measurement_type,
            production_type=production_type,
            start_date=start_date,
            end_date=end_date,
        )
        query = query.order_by(EnergyMeasurement.timestamp).offset(offset).limit(limit)
        measurements = list(self._db.scalars(query).all())
        logger.debug(
            "measurements_selected metric=%s count=%s limit=%s offset=%s",
            metric,
            len(measurements),
            limit,
            offset,
        )
        return measurements

    def list_production_types(self, *, metric: str, source: str | None, zone: str | None) -> list[str]:
        query = select(distinct(EnergyMeasurement.production_type)).where(
            EnergyMeasurement.metric == metric,
            EnergyMeasurement.production_type != "",
            EnergyMeasurement.production_type != "TOTAL",
        )
        if source is not None:
            query = query.where(EnergyMeasurement.source == source)
        if zone is not None:
            query = query.where(EnergyMeasurement.zone == zone)

        return list(self._db.scalars(query).all())

    def latest_before(
        self,
        *,
        metric: str,
        production_type: str,
        timestamp: datetime,
        source: str | None,
        zone: str | None,
    ) -> EnergyMeasurement | None:
        query = select(EnergyMeasurement).where(
            EnergyMeasurement.metric == metric,
            EnergyMeasurement.production_type == production_type,
            EnergyMeasurement.timestamp < timestamp,
        )
        if source is not None:
            query = query.where(EnergyMeasurement.source == source)
        if zone is not None:
            query = query.where(EnergyMeasurement.zone == zone)

        query = query.order_by(EnergyMeasurement.timestamp.desc()).limit(1)
        return self._db.scalars(query).first()

    def at_timestamp(
        self,
        *,
        metric: str,
        production_type: str,
        timestamp: datetime,
        source: str | None,
        zone: str | None,
    ) -> EnergyMeasurement | None:
        query = select(EnergyMeasurement).where(
            EnergyMeasurement.metric == metric,
            EnergyMeasurement.production_type == production_type,
            EnergyMeasurement.timestamp == timestamp,
        )
        if source is not None:
            query = query.where(EnergyMeasurement.source == source)
        if zone is not None:
            query = query.where(EnergyMeasurement.zone == zone)

        return self._db.scalars(query).first()

    def first_after(
        self,
        *,
        metric: str,
        production_type: str,
        timestamp: datetime,
        source: str | None,
        zone: str | None,
    ) -> EnergyMeasurement | None:
        query = select(EnergyMeasurement).where(
            EnergyMeasurement.metric == metric,
            EnergyMeasurement.production_type == production_type,
            EnergyMeasurement.timestamp > timestamp,
        )
        if source is not None:
            query = query.where(EnergyMeasurement.source == source)
        if zone is not None:
            query = query.where(EnergyMeasurement.zone == zone)

        query = query.order_by(EnergyMeasurement.timestamp).limit(1)
        return self._db.scalars(query).first()

    def insert_measurements(self, df: pd.DataFrame) -> int:
        """Insert measurements and ignore rows already present."""
        records = self._prepare_records(df)
        if not records:
            logger.info("measurements_insert_skipped reason=no_records")
            return 0

        statement = insert(EnergyMeasurement.__table__).values(records)
        statement = statement.on_conflict_do_nothing(
            index_elements=[
                "timestamp",
                "source",
                "metric",
                "measurement_type",
                "production_type",
                "zone",
            ]
        ).returning(EnergyMeasurement.id)

        result = self._db.execute(statement)
        self._db.commit()
        inserted_count = len(result.fetchall())
        logger.info(
            "measurements_inserted attempted_count=%s inserted_count=%s skipped_count=%s",
            len(records),
            inserted_count,
            len(records) - inserted_count,
        )
        return inserted_count

    @staticmethod
    def _apply_filters(
        query: Select[tuple[EnergyMeasurement]],
        *,
        metric: str | None,
        source: str | None,
        zone: str | None,
        measurement_type: str | None,
        production_type: str | None,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> Select[tuple[EnergyMeasurement]]:
        if metric is not None:
            query = query.where(EnergyMeasurement.metric == metric)
        if source is not None:
            query = query.where(EnergyMeasurement.source == source)
        if zone is not None:
            query = query.where(EnergyMeasurement.zone == zone)
        if measurement_type is not None:
            query = query.where(EnergyMeasurement.measurement_type == measurement_type)
        if production_type is not None:
            query = query.where(EnergyMeasurement.production_type == production_type)
        if start_date is not None:
            query = query.where(EnergyMeasurement.timestamp >= start_date)
        if end_date is not None:
            query = query.where(EnergyMeasurement.timestamp < end_date)
        return query

    @staticmethod
    def _prepare_records(df: pd.DataFrame) -> list[dict[str, Any]]:
        normalized = df.copy()
        if "type" in normalized.columns and "measurement_type" not in normalized.columns:
            normalized = normalized.rename(columns={"type": "measurement_type"})

        expected_columns = [
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

        for column in expected_columns:
            if column not in normalized.columns:
                normalized[column] = None

        normalized["measurement_type"] = normalized["measurement_type"].fillna("")
        normalized["production_type"] = normalized["production_type"].fillna("")
        normalized = normalized[expected_columns]

        return [
            {
                column: None if pd.isna(value) else value
                for column, value in record.items()
            }
            for record in normalized.to_dict(orient="records")
        ]
