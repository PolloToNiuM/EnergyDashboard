"""Database initialization helpers."""

from app.db.base import Base
from app.db.session import engine
from app.models import EnergyMeasurement


def init_db() -> None:
    """Create database tables declared by SQLAlchemy models."""
    _ = EnergyMeasurement
    Base.metadata.create_all(bind=engine)
