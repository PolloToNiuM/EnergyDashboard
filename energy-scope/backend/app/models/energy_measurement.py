"""Energy measurement database model."""

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EnergyMeasurement(Base):
    """Normalized energy time-series measurement."""

    __tablename__ = "energy_measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    metric: Mapped[str] = mapped_column(String(100), nullable=False)
    measurement_type: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    production_type: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    zone: Mapped[str] = mapped_column(String(100), nullable=False)
    granularity: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "timestamp",
            "source",
            "metric",
            "measurement_type",
            "production_type",
            "zone",
            name="uq_energy_measurement_natural_key",
        ),
        Index("ix_energy_measurements_timestamp_metric", "timestamp", "metric"),
    )
