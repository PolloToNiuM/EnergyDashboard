"""HTTP client for RTE APIs."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv


RTE_API_BASE_URL = "https://digital.iservices.rte-france.com"
RTE_TOKEN_PATH = "/token/oauth/"
RETRYABLE_STATUS_CODES = {429, 500, 503}

logger = logging.getLogger(__name__)


class RTEClientError(RuntimeError):
    """Raised when the RTE client cannot complete a request."""


@dataclass(frozen=True)
class RawAPIResponse:
    """Raw API response plus extraction metadata."""

    source_id: str
    dataset: str
    extracted_at: datetime
    url: str
    status_code: int
    headers: dict[str, str]
    content: bytes
    raw_path: Path
    metadata_path: Path

    @property
    def text(self) -> str:
        return self.content.decode("utf-8")

    def json(self) -> Any:
        return json.loads(self.content)


class RTEClient:
    """Authenticated client for RTE APIs.

    Responsibilities intentionally stay narrow: authenticate, call RTE, handle
    HTTP failures/retries, log outcomes, and persist the raw response.
    """

    def __init__(
        self,
        basic_auth: str,
        *,
        base_url: str = RTE_API_BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff_seconds: float = 1.0,
        raw_data_dir: str | Path | None = None,
        source_id: str = "rte",
    ) -> None:
        if not basic_auth:
            raise ValueError("RTE_BASIC_AUTH is required to initialize RTEClient.")

        self.source_id = source_id
        self._basic_auth = self._normalize_basic_auth(basic_auth)
        self._access_token: str | None = None
        self._token_expires_at = 0.0
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._client = httpx.Client(base_url=base_url, timeout=timeout)
        self._raw_data_dir = Path(raw_data_dir) if raw_data_dir else self._default_raw_data_dir()
        self._source_raw_dir = self._raw_data_dir / self.source_id
        self._ingestion_runs_path = self._raw_data_dir / "ingestion_runs.jsonl"

    @classmethod
    def from_env(cls, env_file: str | Path | None = None, **kwargs: Any) -> "RTEClient":
        """Create the client from environment variables.

        By default, this loads the project-level energy-scope/.env file.
        """
        if env_file is None:
            env_file = Path(__file__).resolve().parents[3] / ".env"

        load_dotenv(env_file)
        return cls(basic_auth=os.getenv("RTE_BASIC_AUTH", ""), **kwargs)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "RTEClient":
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def get_raw(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        dataset: str | None = None,
    ) -> RawAPIResponse:
        """Call an authenticated RTE endpoint and store the raw response."""
        extracted_at = self._now()
        dataset_name = self._dataset_from_path(path) if dataset is None else self._slugify(dataset)
        url = self._build_url(path, params=params)

        try:
            response = self._send_with_retries(
                "GET",
                path,
                params=params,
                headers={"Authorization": f"Bearer {self._get_access_token()}"},
            )
        except Exception as exc:
            error_message = str(exc)
            logger.exception("RTE request failed before receiving a response for %s", url)
            self._record_ingestion_run(
                status="failed",
                extracted_at=extracted_at,
                url=url,
                error=error_message,
            )
            if isinstance(exc, RTEClientError):
                raise
            raise RTEClientError(error_message) from exc

        raw_response = self._store_raw_response(path, dataset_name, extracted_at, response)

        if not response.content:
            message = f"RTE returned an empty response for {url}"
            logger.error(message)
            self._record_ingestion_run(
                status="empty_response",
                extracted_at=extracted_at,
                url=url,
                status_code=response.status_code,
                raw_path=raw_response.raw_path,
                error=message,
            )
            raise RTEClientError(message)

        try:
            self._raise_for_status(response)
        except RTEClientError as exc:
            logger.exception("RTE request returned an HTTP error for %s", url)
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
        return raw_response

    def get_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        """Compatibility helper for jobs that want parsed JSON."""
        return self.get_raw(path, params=params).json()

    def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        response = self._send_with_retries(
            "GET",
            RTE_TOKEN_PATH,
            headers={"Authorization": self._basic_auth},
            save_raw=False,
        )
        self._raise_for_status(response)

        payload = response.json()
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise RTEClientError("RTE token response did not include access_token.")

        expires_in = payload.get("expires_in", 3600)
        self._access_token = access_token
        self._token_expires_at = time.time() + int(expires_in) - 60
        return access_token

    def _send_with_retries(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
        save_raw: bool = True,
    ) -> httpx.Response:
        last_exc: Exception | None = None

        for attempt in range(1, self._max_retries + 2):
            try:
                response = self._client.request(method, path, headers=headers, params=params)
                if response.status_code not in RETRYABLE_STATUS_CODES:
                    return response

                logger.warning(
                    "RTE returned retryable status %s for %s on attempt %s/%s",
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
                    "RTE request transport error for %s on attempt %s/%s: %s",
                    path,
                    attempt,
                    self._max_retries + 1,
                    exc,
                )
                if attempt > self._max_retries:
                    break
                self._sleep_before_retry(response=None, attempt=attempt)

        if save_raw:
            logger.error("RTE request failed before receiving an HTTP response: %s", path)
        raise RTEClientError(str(last_exc) if last_exc else "RTE request failed.")

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
    ) -> RawAPIResponse:
        partition_dir = self._partition_dir(dataset, extracted_at)
        partition_dir.mkdir(parents=True, exist_ok=True)
        content_hash = hashlib.sha256(response.content).hexdigest()[:16]
        endpoint_name = self._slugify(path)
        timestamp = extracted_at.strftime("%Y%m%dT%H%M%S%fZ")
        extension = self._extension_from_response(response)
        raw_path = partition_dir / f"{timestamp}_{endpoint_name}_{content_hash}{extension}"
        metadata_path = raw_path.with_suffix(f"{raw_path.suffix}.metadata.json")

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

        return RawAPIResponse(
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
    def _normalize_basic_auth(value: str) -> str:
        value = value.strip()
        if value.lower().startswith("basic "):
            return value
        return f"Basic {value}"

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RTEClientError(
                f"RTE request failed with status {exc.response.status_code}: "
                f"{exc.response.text}"
            ) from exc

    @staticmethod
    def _write_new_file(path: Path, content: bytes) -> None:
        try:
            with path.open("xb") as file:
                file.write(content)
        except FileExistsError as exc:
            raise RTEClientError(f"Refusing to overwrite existing raw file: {path}") from exc

    @staticmethod
    def _extension_from_response(response: httpx.Response) -> str:
        content_type = response.headers.get("Content-Type", "").lower()
        if "json" in content_type:
            return ".json"
        if "csv" in content_type:
            return ".csv"
        if "xml" in content_type:
            return ".xml"
        return ".bin"

    @staticmethod
    def _slugify(value: str) -> str:
        value = value.strip("/") or "root"
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
        return slug[:120] or "endpoint"

    @classmethod
    def _dataset_from_path(cls, path: str) -> str:
        parts = [part for part in path.strip("/").split("/") if part]
        try:
            open_api_index = parts.index("open_api")
        except ValueError:
            return cls._slugify(parts[0] if parts else "unknown")

        dataset_index = open_api_index + 1
        if dataset_index >= len(parts):
            return "unknown"
        return cls._slugify(parts[dataset_index])

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _default_raw_data_dir() -> Path:
        return Path(__file__).resolve().parents[3] / "data" / "raw"
