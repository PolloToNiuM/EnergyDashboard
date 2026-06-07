"""HTTP client for Open-Meteo weather APIs."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import httpx


OPEN_METEO_ARCHIVE_BASE_URL = "https://archive-api.open-meteo.com"
OPEN_METEO_ARCHIVE_PATH = "/v1/archive"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

logger = logging.getLogger(__name__)


class WeatherClientError(RuntimeError):
    """Raised when the weather client cannot complete a request."""


@dataclass(frozen=True)
class WeatherRawResponse:
    """Raw Open-Meteo response plus extraction metadata."""

    source_id: str
    dataset: str
    extracted_at: datetime
    url: str
    status_code: int
    headers: dict[str, str]
    content: bytes
    raw_path: Path
    metadata_path: Path

    def json(self) -> Any:
        return json.loads(self.content)


class WeatherClient:
    """Client for Open-Meteo APIs with raw persistence and retries."""

    def __init__(
        self,
        *,
        base_url: str = OPEN_METEO_ARCHIVE_BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff_seconds: float = 1.0,
        raw_data_dir: str | Path | None = None,
        source_id: str = "open_meteo",
    ) -> None:
        self.source_id = source_id
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._client = httpx.Client(base_url=base_url, timeout=timeout)
        self._raw_data_dir = Path(raw_data_dir) if raw_data_dir else self._default_raw_data_dir()
        self._source_raw_dir = self._raw_data_dir / self.source_id
        self._ingestion_runs_path = self._raw_data_dir / "ingestion_runs.jsonl"

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "WeatherClient":
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def get_hourly_weather(
        self,
        *,
        latitude: float,
        longitude: float,
        start_date: str,
        end_date: str,
        hourly: list[str] | tuple[str, ...] = ("temperature_2m",),
        timezone: str = "Europe/Paris",
        dataset: str = "weather_hourly",
    ) -> WeatherRawResponse:
        """Fetch hourly historical weather data from Open-Meteo."""
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": ",".join(hourly),
            "timezone": timezone,
        }
        return self.get_raw(OPEN_METEO_ARCHIVE_PATH, params=params, dataset=dataset)

    def get_raw(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        dataset: str = "weather",
    ) -> WeatherRawResponse:
        """Call Open-Meteo and store the raw response."""
        extracted_at = self._now()
        dataset_name = self._slugify(dataset)
        url = self._build_url(path, params=params)

        try:
            response = self._send_with_retries("GET", path, params=params)
        except Exception as exc:
            logger.exception("Open-Meteo request failed before receiving a response for %s", url)
            self._record_ingestion_run(
                status="failed",
                extracted_at=extracted_at,
                url=url,
                error=str(exc),
            )
            if isinstance(exc, WeatherClientError):
                raise
            raise WeatherClientError(str(exc)) from exc

        raw_response = self._store_raw_response(path, dataset_name, extracted_at, response)

        if not response.content:
            message = f"Open-Meteo returned an empty response for {url}"
            logger.error(message)
            self._record_ingestion_run(
                status="empty_response",
                extracted_at=extracted_at,
                url=url,
                status_code=response.status_code,
                raw_path=raw_response.raw_path,
                error=message,
            )
            raise WeatherClientError(message)

        try:
            self._raise_for_status(response)
        except WeatherClientError as exc:
            logger.exception("Open-Meteo request returned an HTTP error for %s", url)
            self._record_ingestion_run(
                status="failed",
                extracted_at=extracted_at,
                url=url,
                status_code=response.status_code,
                raw_path=raw_response.raw_path,
                error=str(exc),
            )
            raise

        self._record_ingestion_run(
            status="success",
            extracted_at=extracted_at,
            url=url,
            status_code=response.status_code,
            raw_path=raw_response.raw_path,
        )
        logger.info("open_meteo_raw_saved dataset=%s raw_path=%s", dataset_name, raw_response.raw_path)
        return raw_response

    def _send_with_retries(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        last_exc: Exception | None = None

        for attempt in range(1, self._max_retries + 2):
            try:
                response = self._client.request(method, path, params=params)
                if response.status_code not in RETRYABLE_STATUS_CODES:
                    return response

                logger.warning(
                    "Open-Meteo returned retryable status %s for %s on attempt %s/%s",
                    response.status_code,
                    response.url,
                    attempt,
                    self._max_retries + 1,
                )
                if attempt > self._max_retries:
                    return response
                self._sleep_before_retry(response=response, attempt=attempt)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                logger.warning(
                    "Open-Meteo transport error for %s on attempt %s/%s: %s",
                    path,
                    attempt,
                    self._max_retries + 1,
                    exc,
                )
                if attempt > self._max_retries:
                    break
                self._sleep_before_retry(response=None, attempt=attempt)

        raise WeatherClientError(str(last_exc) if last_exc else "Open-Meteo request failed.")

    def _sleep_before_retry(self, *, response: httpx.Response | None, attempt: int) -> None:
        retry_after = self._retry_after_seconds(response)
        delay = retry_after if retry_after is not None else self._retry_backoff_seconds * attempt
        time.sleep(delay)

    @staticmethod
    def _retry_after_seconds(response: httpx.Response | None) -> float | None:
        if response is None:
            return None

        value = response.headers.get("Retry-After")
        if not value:
            return None
        if value.isdigit():
            return float(value)

        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        return max(0.0, (retry_at - datetime.now(retry_at.tzinfo or UTC)).total_seconds())

    def _store_raw_response(
        self,
        path: str,
        dataset: str,
        extracted_at: datetime,
        response: httpx.Response,
    ) -> WeatherRawResponse:
        partition_dir = self._partition_dir(dataset, extracted_at)
        partition_dir.mkdir(parents=True, exist_ok=True)
        content_hash = hashlib.sha256(response.content).hexdigest()[:16]
        endpoint_name = self._slugify(path)
        timestamp = extracted_at.strftime("%Y%m%dT%H%M%S%fZ")
        raw_path = partition_dir / f"{timestamp}_{endpoint_name}_{content_hash}.json"
        metadata_path = raw_path.with_suffix(".json.metadata.json")

        self._write_new_file(raw_path, response.content)
        metadata = {
            "source_id": self.source_id,
            "dataset": dataset,
            "extracted_at": extracted_at.isoformat(),
            "url": str(response.url),
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "content_sha256": hashlib.sha256(response.content).hexdigest(),
        }
        self._write_new_file(
            metadata_path,
            json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8"),
        )

        return WeatherRawResponse(
            source_id=self.source_id,
            dataset=dataset,
            extracted_at=extracted_at,
            url=str(response.url),
            status_code=response.status_code,
            headers=dict(response.headers),
            content=response.content,
            raw_path=raw_path,
            metadata_path=metadata_path,
        )

    def _record_ingestion_run(
        self,
        *,
        status: str,
        extracted_at: datetime,
        url: str,
        status_code: int | None = None,
        raw_path: Path | None = None,
        error: str | None = None,
    ) -> None:
        self._raw_data_dir.mkdir(parents=True, exist_ok=True)
        event = {
            "source_id": self.source_id,
            "extracted_at": extracted_at.isoformat(),
            "url": url,
            "status": status,
            "status_code": status_code,
            "raw_path": str(raw_path) if raw_path else None,
            "error": error,
        }
        with self._ingestion_runs_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _partition_dir(self, dataset: str, extracted_at: datetime) -> Path:
        return (
            self._source_raw_dir
            / dataset
            / f"year={extracted_at.year}"
            / f"month={extracted_at.month:02d}"
            / f"day={extracted_at.day:02d}"
        )

    def _build_url(self, path: str, *, params: dict[str, Any] | None = None) -> str:
        return str(self._client.build_request("GET", path, params=params).url)

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise WeatherClientError(
                f"Open-Meteo request failed with status {exc.response.status_code}: "
                f"{exc.response.text}"
            ) from exc

    @staticmethod
    def _write_new_file(path: Path, content: bytes) -> None:
        try:
            with path.open("xb") as file:
                file.write(content)
        except FileExistsError as exc:
            raise WeatherClientError(f"Refusing to overwrite existing raw file: {path}") from exc

    @staticmethod
    def _slugify(value: str) -> str:
        value = value.strip("/") or "root"
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
        return slug[:120] or "endpoint"

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _default_raw_data_dir() -> Path:
        return Path(__file__).resolve().parents[3] / "data" / "raw"
