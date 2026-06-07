"""Helpers to save transformed dataframes in data/processed."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
logger = logging.getLogger(__name__)


class ProcessedLoaderError(RuntimeError):
    """Raised when processed data cannot be saved or loaded."""


def save_dataframe_parquet(
    df: pd.DataFrame,
    *,
    dataset: str,
    processed_data_dir: str | Path = DEFAULT_PROCESSED_DATA_DIR,
    extracted_at: datetime | None = None,
) -> Path:
    """Save a transformed dataframe as a partitioned Parquet file."""
    if df.empty:
        logger.error("processed_save_failed dataset=%s reason=empty_dataframe", dataset)
        raise ProcessedLoaderError(f"Refusing to save empty dataframe for '{dataset}'.")

    extracted_at = extracted_at or datetime.now(UTC)
    target_dir = (
        Path(processed_data_dir)
        / dataset
        / f"year={extracted_at.year}"
        / f"month={extracted_at.month:02d}"
        / f"day={extracted_at.day:02d}"
    )
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = extracted_at.strftime("%Y%m%dT%H%M%S%fZ")
    file_path = target_dir / f"{timestamp}.parquet"
    if file_path.exists():
        logger.error("processed_save_failed path=%s reason=file_exists", file_path)
        raise ProcessedLoaderError(f"Refusing to overwrite processed file: {file_path}")

    df.to_parquet(file_path, index=False)
    logger.info("processed_parquet_saved dataset=%s rows=%s path=%s", dataset, len(df), file_path)
    return file_path


def load_dataframe_parquet(path: str | Path) -> pd.DataFrame:
    """Load a processed Parquet file."""
    df = pd.read_parquet(path)
    logger.info("processed_parquet_loaded path=%s rows=%s", path, len(df))
    return df
