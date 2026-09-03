from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from api.routes import router as api_router
from database import repositories
from services.processing_service import ProcessingService
from services.worker import Worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB

def get_cors_origins() -> list[str]:
    """Parse CORS_ORIGINS environment variable into a list of origins."""
    raw = os.getenv("CORS_ORIGINS", "")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


class UploadSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and request.url.path == "/api/jobs":
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    size = int(content_length)
                    if size > MAX_UPLOAD_SIZE:
                        return JSONResponse(
                            status_code=413,
                            content={"detail": f"Upload too large. Maximum size is {MAX_UPLOAD_SIZE} bytes."},
                        )
                except ValueError:
                    pass
        return await call_next(request)


async def _run_startup_recovery() -> None:
    """
    Recover jobs that were interrupted by a container restart.

    Finds jobs with status 'queued' or 'processing' that have pending/processing rows.
    Resets processing rows to pending, resets job status to queued, and starts a worker.
    """
    logger.info("Running startup recovery check...")

    recoverable_jobs = repositories.get_recoverable_jobs()

    if not recoverable_jobs:
        logger.info("No recoverable jobs found")
        return

    logger.info("Found %d recoverable job(s)", len(recoverable_jobs))

    processing_service = ProcessingService()
    worker = Worker(processing_service)

    for job in recoverable_jobs:
        job_id = str(job.id)
        logger.info("[JOB %s] Starting recovery", job_id)

        # Reset any rows stuck in 'processing' back to 'pending'
        # Preserves attempts count
        reset_count = repositories.reset_processing_rows(job.id)
        if reset_count > 0:
            logger.info("[JOB %s] Reset %d processing row(s) to pending", job_id, reset_count)

        # Reset job status to 'queued' so worker.run_job will transition it to 'processing'
        repositories.reset_job_for_recovery(job.id)

        # Start the worker for this job (non-blocking)
        # Using a background task would require FastAPI's BackgroundTasks which isn't
        # available here, so we run it in a thread
        import threading

        def run_worker():
            try:
                worker.run_job(job_id)
            except Exception:
                logger.exception("[JOB %s] Worker crashed during recovery", job_id)

        thread = threading.Thread(target=run_worker, daemon=True, name=f"worker-{job_id[:8]}")
        thread.start()
        logger.info("[JOB %s] Recovery worker started", job_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup")
    await _run_startup_recovery()
    yield
    logger.info("Application shutdown")


app = FastAPI(
    title="UniLog Enricher API",
    description="Product enrichment API using research and extraction pipeline",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(UploadSizeLimitMiddleware)
cors_origins = get_cors_origins()
if not cors_origins:
    logger.warning("CORS_ORIGINS not set or empty. CORS will be disabled for security.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health_check():
    return {"status": "ok"}