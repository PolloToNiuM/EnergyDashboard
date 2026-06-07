"""Load transformed dataframes into PostgreSQL."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from energy_ingestion.quality.checks import validate_measurements_dataframe


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = PROJECT_ROOT / "backend"
DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://energy_scope:energy_scope@localhost:5432/energy_scope"
)

if str(BACKEND_ROOT) not in sys.path:
    sys.path.append(str(BACKEND_ROOT))

from app.db.base import Base
from app.models.energy_measurement import EnergyMeasurement


logger = logging.getLogger(__name__)


class PostgresLoaderError(RuntimeError):
    """Raised when data cannot be inserted into PostgreSQL."""


def get_database_url(env_file: str | Path | None = None) -> str:
    """Load DATABASE_URL from energy-scope/.env when available."""
    if env_file is None:
        env_file = PROJECT_ROOT / ".env"
    load_dotenv(env_file)
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def create_postgres_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine for PostgreSQL."""
    return create_engine(database_url or get_database_url())


def init_postgres_schema(engine: Engine | None = None) -> None:
    """Create SQLAlchemy tables used by ingestion."""
    engine = engine or create_postgres_engine()
    logger.info("postgres_schema_initializing")
    Base.metadata.create_all(bind=engine)
    _sync_energy_measurements_schema(engine)
    logger.info("postgres_schema_initialized")


def insert_energy_measurements(
    df: pd.DataFrame,
    *,
    engine: Engine | None = None,
    create_schema: bool = True,
) -> int:
    """Insert transformed energy measurements and skip existing duplicates."""
    if df.empty:
        logger.error("postgres_insert_failed reason=empty_dataframe")
        raise PostgresLoaderError("Refusing to insert an empty dataframe.")

    validated_df = validate_measurements_dataframe(df)

    engine = engine or create_postgres_engine()
    if create_schema:
        init_postgres_schema(engine)

    records = _prepare_energy_measurement_records(validated_df)
    if not records:
        logger.info("postgres_insert_skipped reason=no_records")
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

    with engine.begin() as connection:
        result = connection.execute(statement)

    inserted_count = len(result.fetchall())
    logger.info(
        "postgres_measurements_inserted attempted_count=%s inserted_count=%s skipped_count=%s",
        len(records),
        inserted_count,
        len(records) - inserted_count,
    )
    return inserted_count


def _prepare_energy_measurement_records(df: pd.DataFrame) -> list[dict[str, Any]]:
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


def _sync_energy_measurements_schema(engine: Engine) -> None:
    """Add columns needed by ingestion when the table already exists."""
    statements = [
        "ALTER TABLE energy_measurements ADD COLUMN IF NOT EXISTS end_date TIMESTAMPTZ",
        "ALTER TABLE energy_measurements ADD COLUMN IF NOT EXISTS updated_date TIMESTAMPTZ",
        (
            "ALTER TABLE energy_measurements "
            "ADD COLUMN IF NOT EXISTS measurement_type VARCHAR(100) NOT NULL DEFAULT ''"
        ),
        (
            "ALTER TABLE energy_measurements "
            "ADD COLUMN IF NOT EXISTS production_type VARCHAR(100) NOT NULL DEFAULT ''"
        ),
        (
            "ALTER TABLE energy_measurements "
            "DROP CONSTRAINT IF EXISTS uq_energy_measurements_measurement_key"
        ),
        "DROP INDEX IF EXISTS uq_energy_measurements_measurement_key",
        (
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_energy_measurement_natural_key "
            "ON energy_measurements "
            "(timestamp, source, metric, measurement_type, production_type, zone)"
        ),
    ]

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
