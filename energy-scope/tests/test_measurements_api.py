"""Smoke tests for measurement API routes."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.routes import measurements as measurements_routes
from app.db.session import get_db
from app.main import app


class FakeMeasurementService:
    """Service fake used to keep API tests independent from PostgreSQL."""

    def __init__(self, db) -> None:
        self._db = db

    def list_measurements(self, **kwargs):
        return [
            SimpleNamespace(
                id=1,
                timestamp=datetime(2026, 6, 1, 0, 0, tzinfo=UTC),
                end_date=datetime(2026, 6, 1, 0, 15, tzinfo=UTC),
                updated_date=datetime(2026, 6, 1, 0, 20, tzinfo=UTC),
                source="RTE",
                metric="consumption_short_term",
                measurement_type="REALISED",
                production_type="",
                value=40685.0,
                unit="MW",
                zone="France",
                granularity="15min",
                created_at=datetime(2026, 6, 1, 0, 30, tzinfo=UTC),
                is_interpolated=False,
            )
        ]

    def data_quality_summary(self, dataset):
        return {
            "dataset": dataset,
            "metric": "consumption_short_term",
            "total_rows": 2,
            "passed": True,
            "score": 100.0,
            "checks": [
                {
                    "name": "timestamp_not_null",
                    "label": "Timestamp non null",
                    "invalid_count": 0,
                    "passed": True,
                }
            ],
        }


def override_get_db():
    yield object()


def test_measurements_endpoint_returns_200(monkeypatch) -> None:
    monkeypatch.setattr(
        measurements_routes,
        "MeasurementService",
        FakeMeasurementService,
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        response = TestClient(app).get(
            "/measurements",
            params={"metric": "consumption_short_term", "limit": 10},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    assert response.json()[0]["metric"] == "consumption_short_term"
    assert response.json()[0]["measurement_type"] == "REALISED"


def test_measurements_quality_endpoint_returns_200(monkeypatch) -> None:
    monkeypatch.setattr(
        measurements_routes,
        "MeasurementService",
        FakeMeasurementService,
    )
    app.dependency_overrides[get_db] = override_get_db

    try:
        response = TestClient(app).get(
            "/measurements/quality",
            params={"dataset": "consumption"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    assert response.json()["dataset"] == "consumption"
    assert response.json()["passed"] is True
