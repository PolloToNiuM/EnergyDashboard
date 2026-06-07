"""Helpers to load raw files saved by API clients."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"


class RawLoaderError(RuntimeError):
    """Raised when a raw file cannot be loaded."""


class RawLoader:
    """Load raw API responses and their metadata from data/raw."""

    def __init__(self, raw_data_dir: str | Path = DEFAULT_RAW_DATA_DIR) -> None:
        self.raw_data_dir = Path(raw_data_dir)

    def list_files(
        self,
        source_id: str,
        dataset: str | None = None,
        pattern: str = "*",
    ) -> list[Path]:
        """Return raw files for one source, excluding metadata files."""
        search_dir = self.raw_data_dir / source_id
        if dataset is not None:
            search_dir = search_dir / dataset

        if not search_dir.exists():
            return []

        return sorted(
            path
            for path in search_dir.rglob(pattern)
            if path.is_file() and not path.name.endswith(".metadata.json")
        )

    def latest_file(
        self,
        source_id: str,
        dataset: str | None = None,
        pattern: str = "*",
    ) -> Path:
        """Return the latest raw file for one source."""
        files = self.list_files(source_id, dataset=dataset, pattern=pattern)
        if not files:
            target = f"{source_id}/{dataset}" if dataset else source_id
            raise RawLoaderError(f"No raw files found for source '{target}'.")
        return files[-1]

    def load_bytes(self, path: str | Path) -> bytes:
        """Load a raw file as bytes."""
        return Path(path).read_bytes()

    def load_text(self, path: str | Path, encoding: str = "utf-8") -> str:
        """Load a raw file as text."""
        return Path(path).read_text(encoding=encoding)

    def load_json(self, path: str | Path) -> Any:
        """Load a raw JSON file."""
        with Path(path).open(encoding="utf-8") as file:
            return json.load(file)

    def load_metadata(self, raw_path: str | Path) -> dict[str, Any]:
        """Load the metadata file associated with a raw file."""
        raw_path = Path(raw_path)
        metadata_path = raw_path.with_suffix(f"{raw_path.suffix}.metadata.json")
        if not metadata_path.exists():
            raise RawLoaderError(f"Metadata file not found: {metadata_path}")

        with metadata_path.open(encoding="utf-8") as file:
            return json.load(file)
