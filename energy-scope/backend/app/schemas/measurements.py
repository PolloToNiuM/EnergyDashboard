"""Schemas for measurement API responses."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MeasurementRead(BaseModel):
    """Serialized energy measurement."""

    model_config = ConfigDict(from_attributes=True)

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
    is_interpolated: bool = False


class MeasurementSyncResult(BaseModel):
    """Result of a measurement synchronization request."""

    dataset: str
    date: str
    inserted_count: int
