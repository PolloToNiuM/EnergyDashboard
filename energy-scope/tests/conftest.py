"""Pytest configuration shared by project tests."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
INGESTION_ROOT = PROJECT_ROOT / "ingestion"

for path in (BACKEND_ROOT, INGESTION_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
