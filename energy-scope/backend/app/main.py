"""Backend application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.measurements import router as measurements_router

app = FastAPI(title="Energy Scope API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(measurements_router)


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    """Basic liveness endpoint for local and container health checks."""
    return {"status": "ok"}
