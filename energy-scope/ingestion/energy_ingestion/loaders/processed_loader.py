"""Helpers to save transformed dataframes in data/processed."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"


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
        raise ProcessedLoaderError(f"Refusing to overwrite processed file: {file_path}")

    df.to_parquet(file_path, index=False)
    return file_path


def load_dataframe_parquet(path: str | Path) -> pd.DataFrame:
    """Load a processed Parquet file."""
    return pd.read_parquet(path)
