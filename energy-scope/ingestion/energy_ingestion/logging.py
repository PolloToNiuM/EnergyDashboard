"""Logging configuration for standalone ingestion jobs."""

from __future__ import annotations

import logging
import os
from logging.config import dictConfig
from pathlib import Path

from dotenv import load_dotenv


DEFAULT_LOG_LEVEL = "INFO"


def configure_logging() -> None:
    """Configure console logs for ingestion commands."""
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    log_level = os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "level": log_level,
                "handlers": ["default"],
            },
        }
    )
