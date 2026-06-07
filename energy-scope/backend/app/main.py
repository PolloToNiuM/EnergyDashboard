"""Backend application entrypoint."""

import logging
from contextlib import asynccontextmanager
from time import perf_counter
from time import sleep

from fastapi import FastAPI
from sqlalchemy.exc import SQLAlchemyError
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.api.routes.measurements import router as measurements_router
from app.core.logging import configure_logging, new_request_id, request_id_context
from app.db.init_db import init_db

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Initialize required infrastructure before serving requests."""
    _ = application
    init_db_with_retry()
    yield


def init_db_with_retry(max_attempts: int = 10, delay_seconds: float = 2.0) -> None:
    """Create tables once PostgreSQL is reachable."""
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info("database_initialization_started attempt=%s", attempt)
            init_db()
            logger.info("database_initialization_finished")
            return
        except SQLAlchemyError:
            logger.exception(
                "database_initialization_failed attempt=%s max_attempts=%s",
                attempt,
                max_attempts,
            )
            if attempt == max_attempts:
                raise
            sleep(delay_seconds)


app = FastAPI(title="Energy Scope API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(measurements_router)


@app.middleware("http")
async def log_requests(request: Request, call_next) -> Response:
    """Log request lifecycle with a short correlation id."""
    request_id = request.headers.get("X-Request-ID") or new_request_id()
    token = request_id_context.set(request_id)
    start_time = perf_counter()

    try:
        logger.info("request_started method=%s path=%s", request.method, request.url.path)
        response = await call_next(request)
    except Exception:
        duration_ms = (perf_counter() - start_time) * 1000
        logger.exception(
            "request_failed method=%s path=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            duration_ms,
        )
        request_id_context.reset(token)
        raise

    duration_ms = (perf_counter() - start_time) * 1000
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_finished method=%s path=%s status_code=%s duration_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    request_id_context.reset(token)
    return response


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    """Basic liveness endpoint for local and container health checks."""
    return {"status": "ok"}
