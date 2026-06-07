"""Measurement API routes."""

import logging
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.measurements import MeasurementRead, MeasurementSyncResult
from app.services.measurements import MeasurementService


router = APIRouter(prefix="/measurements", tags=["measurements"])
logger = logging.getLogger(__name__)


@router.get("", response_model=list[MeasurementRead])
def list_measurements(
    db: Annotated[Session, Depends(get_db)],
    metric: str | None = None,
    source: str | None = None,
    zone: str | None = None,
    measurement_type: str | None = None,
    production_type: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[MeasurementRead]:
    """Return normalized energy measurements."""
    logger.info(
        "list_measurements metric=%s source=%s zone=%s measurement_type=%s "
        "production_type=%s start_date=%s end_date=%s limit=%s offset=%s",
        metric,
        source,
        zone,
        measurement_type,
        production_type,
        start_date,
        end_date,
        limit,
        offset,
    )
    service = MeasurementService(db)
    measurements = service.list_measurements(
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
    logger.info("list_measurements_finished count=%s", len(measurements))
    return measurements


@router.post("/sync/actual-generation", response_model=MeasurementSyncResult)
def sync_actual_generation(
    db: Annotated[Session, Depends(get_db)],
    date_: Annotated[date, Query(alias="date")],
) -> MeasurementSyncResult:
    """Fetch actual generation from RTE for one day and insert it."""
    if date_ > date.today():
        logger.warning("sync_actual_generation_rejected date=%s reason=future_date", date_)
        raise HTTPException(
            status_code=400,
            detail="Future dates cannot be synchronized.",
        )

    logger.info("sync_actual_generation_started date=%s", date_)
    service = MeasurementService(db)
    inserted_count = service.sync_actual_generation_for_date(date_)
    logger.info(
        "sync_actual_generation_finished date=%s inserted_count=%s",
        date_,
        inserted_count,
    )
    return MeasurementSyncResult(
        dataset="actual_generation",
        date=date_.isoformat(),
        inserted_count=inserted_count,
    )


@router.post("/sync/consumption", response_model=MeasurementSyncResult)
def sync_consumption(
    db: Annotated[Session, Depends(get_db)],
    date_: Annotated[date, Query(alias="date")],
) -> MeasurementSyncResult:
    """Fetch short-term consumption from RTE for one day and insert it."""
    if date_ > date.today():
        logger.warning("sync_consumption_rejected date=%s reason=future_date", date_)
        raise HTTPException(
            status_code=400,
            detail="Future dates cannot be synchronized.",
        )

    logger.info("sync_consumption_started date=%s", date_)
    service = MeasurementService(db)
    inserted_count = service.sync_consumption_for_date(date_)
    logger.info(
        "sync_consumption_finished date=%s inserted_count=%s",
        date_,
        inserted_count,
    )
    return MeasurementSyncResult(
        dataset="consumption",
        date=date_.isoformat(),
        inserted_count=inserted_count,
    )


@router.post("/sync/weather", response_model=MeasurementSyncResult)
def sync_weather(
    db: Annotated[Session, Depends(get_db)],
    date_: Annotated[date, Query(alias="date")],
) -> MeasurementSyncResult:
    """Fetch averaged Open-Meteo weather for one day and insert it."""
    if date_ > date.today():
        logger.warning("sync_weather_rejected date=%s reason=future_date", date_)
        raise HTTPException(
            status_code=400,
            detail="Future dates cannot be synchronized.",
        )

    logger.info("sync_weather_started date=%s", date_)
    service = MeasurementService(db)
    inserted_count = service.sync_weather_for_date(date_)
    logger.info(
        "sync_weather_finished date=%s inserted_count=%s",
        date_,
        inserted_count,
    )
    return MeasurementSyncResult(
        dataset="weather",
        date=date_.isoformat(),
        inserted_count=inserted_count,
    )
