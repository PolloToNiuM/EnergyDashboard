"""Logging configuration for the backend and imported project modules."""

from __future__ import annotations

import logging
import os
from contextvars import ContextVar
from logging.config import dictConfig
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv


DEFAULT_LOG_LEVEL = "INFO"
request_id_context: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Attach the current request id to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_context.get()
        return True


def configure_logging() -> None:
    """Configure application logging once at startup/import time."""
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    log_level = os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "request_id": {
                    "()": "app.core.logging.RequestIdFilter",
                },
            },
            "formatters": {
                "default": {
                    "format": (
                        "%(asctime)s %(levelname)s [%(name)s] "
                        "[request_id=%(request_id)s] %(message)s"
                    ),
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "filters": ["request_id"],
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "level": log_level,
                "handlers": ["default"],
            },
            "loggers": {
                "uvicorn": {
                    "level": log_level,
                    "handlers": ["default"],
                    "propagate": False,
                },
                "uvicorn.error": {
                    "level": log_level,
                    "handlers": ["default"],
                    "propagate": False,
                },
                "uvicorn.access": {
                    "level": os.getenv("UVICORN_ACCESS_LOG_LEVEL", "WARNING").upper(),
                    "handlers": ["default"],
                    "propagate": False,
                },
                "httpx": {
                    "level": os.getenv("HTTPX_LOG_LEVEL", "WARNING").upper(),
                    "handlers": ["default"],
                    "propagate": False,
                },
                "httpcore": {
                    "level": os.getenv("HTTPCORE_LOG_LEVEL", "WARNING").upper(),
                    "handlers": ["default"],
                    "propagate": False,
                },
                "sqlalchemy.engine": {
                    "level": os.getenv("SQLALCHEMY_LOG_LEVEL", "WARNING").upper(),
                    "handlers": ["default"],
                    "propagate": False,
                },
            },
        }
    )


def new_request_id() -> str:
    """Generate a compact request id for correlating logs."""
    return uuid4().hex[:12]
