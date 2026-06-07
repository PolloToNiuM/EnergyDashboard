"""Tests for raw data file loading helpers."""

from __future__ import annotations

import json

import pytest

from energy_ingestion.loaders.raw_loader import RawLoader, RawLoaderError


def test_raw_loader_lists_and_loads_raw_json_with_metadata(tmp_path) -> None:
    raw_root = tmp_path / "raw"
    dataset_dir = raw_root / "rte" / "consumption" / "year=2026" / "month=06" / "day=01"
    dataset_dir.mkdir(parents=True)
    raw_path = dataset_dir / "20260601T000000Z_consumption.json"
    metadata_path = raw_path.with_suffix(".json.metadata.json")

    raw_payload = {"short_term": [{"type": "REALISED", "values": []}]}
    metadata_payload = {
        "source_id": "rte",
        "dataset": "consumption",
        "status_code": 200,
    }
    raw_path.write_text(json.dumps(raw_payload), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata_payload), encoding="utf-8")

    loader = RawLoader(raw_data_dir=raw_root)

    files = loader.list_files("rte", dataset="consumption", pattern="*.json")

    assert files == [raw_path]
    assert loader.latest_file("rte", dataset="consumption", pattern="*.json") == raw_path
    assert loader.load_json(raw_path) == raw_payload
    assert loader.load_metadata(raw_path) == metadata_payload


def test_raw_loader_raises_when_latest_file_is_missing(tmp_path) -> None:
    loader = RawLoader(raw_data_dir=tmp_path / "raw")

    with pytest.raises(RawLoaderError):
        loader.latest_file("rte", dataset="missing")
