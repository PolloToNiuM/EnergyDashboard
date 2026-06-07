"""Measurement API routes."""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.measurements import MeasurementRead, MeasurementSyncResult
from app.services.measurements import MeasurementService


router = APIRouter(prefix="/measurements", tags=["measurements"])


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
    service = MeasurementService(db)
    return service.list_measurements(
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


@router.post("/sync/actual-generation", response_model=MeasurementSyncResult)
def sync_actual_generation(
    db: Annotated[Session, Depends(get_db)],
    date_: Annotated[date, Query(alias="date")],
) -> MeasurementSyncResult:
    """Fetch actual generation from RTE for one day and insert it."""
    if date_ > date.today():
        raise HTTPException(
            status_code=400,
            detail="Future dates cannot be synchronized.",
        )

    service = MeasurementService(db)
    inserted_count = service.sync_actual_generation_for_date(date_)
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
        raise HTTPException(
            status_code=400,
            detail="Future dates cannot be synchronized.",
        )

    service = MeasurementService(db)
    inserted_count = service.sync_consumption_for_date(date_)
    return MeasurementSyncResult(
        dataset="consumption",
        date=date_.isoformat(),
        inserted_count=inserted_count,
    )
