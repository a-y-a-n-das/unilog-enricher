from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from api.models import (
    ErrorResponse,
    JobCreateResponse,
    JobRowResponse,
    JobStatusResponse,
    JobListResponse,
    RetryFailedResponse,
)
from api.storage import (
    get_output_file_path,
    resolve_safe_output_path,
    save_upload_file,
)
from api.output_generator import generate_output, generate_partial_output
from database import repositories
from database.models import Job
from models.input_models import InputRecord
from pipeline.input.csv import load_input_csv
from pipeline.input.xlsx import load_input_xlsx
from services.job_service import ValidationError, create_job, get_job_status, retry_failed_rows
from services.processing_service import ProcessingService
from services.worker import Worker

if TYPE_CHECKING:
    from database.models import JobRow

router = APIRouter()
logger = logging.getLogger(__name__)


def get_processing_service() -> ProcessingService:
    return ProcessingService()


def get_worker(processing_service: ProcessingService = Depends(get_processing_service)) -> Worker:
    return Worker(processing_service)


@router.post(
    "/jobs",
    response_model=JobCreateResponse,
    status_code=202,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid file or validation error"},
        415: {"model": ErrorResponse, "description": "Unsupported file format"},
    },
)
async def create_job_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    worker: Worker = Depends(get_worker),
) -> JobCreateResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing file")

    ext = file.filename.lower().split(".")[-1]
    if ext not in ("csv", "xlsx"):
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file format: .{ext}. Supported: .csv, .xlsx",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    from uuid import uuid4
    job_id = str(uuid4())

    file_path = save_upload_file(job_id, file.filename, content)

    try:
        if ext == "csv":
            records = load_input_csv(file_path)
        else:
            records = load_input_xlsx(file_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Failed to parse input file")
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {e}")

    if not records:
        raise HTTPException(status_code=400, detail="No valid data rows found in file")

    try:
        job = create_job(
            input_filename=file.filename,
            input_format=ext,
            input_file_path=str(file_path),
            rows=records,
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    background_tasks.add_task(worker.run_job, str(job.id))

    return JobCreateResponse(
        job_id=str(job.id),
        status=job.status,
        total_rows=job.total_rows,
    )


@router.get(
    "/jobs",
    response_model=JobListResponse,
)
async def list_jobs_endpoint() -> JobListResponse:
    jobs = repositories.get_all_jobs()
    from api.models import make_job_status_response
    return JobListResponse(jobs=[make_job_status_response(job) for job in jobs])


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    responses={404: {"model": ErrorResponse, "description": "Job not found"}},
)
async def get_job_status_endpoint(job_id: str) -> JobStatusResponse:
    job = repositories.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    from api.models import make_job_status_response
    return make_job_status_response(job)


@router.get(
    "/jobs/{job_id}/rows",
    response_model=list[JobRowResponse],
    responses={404: {"model": ErrorResponse, "description": "Job not found"}},
)
async def get_job_rows_endpoint(job_id: str) -> list[JobRowResponse]:
    job = repositories.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    from database.connection import SessionLocal
    from database.models import JobRow
    from sqlalchemy import select

    with SessionLocal() as session:
        rows = session.execute(
            select(JobRow)
            .where(JobRow.job_id == job.id)
            .order_by(JobRow.row_number)
        ).scalars().all()

    from api.models import make_job_row_response
    return [make_job_row_response(row) for row in rows]


@router.post(
    "/jobs/{job_id}/retry-failed",
    response_model=RetryFailedResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Job not found"},
    },
)
async def retry_failed_rows_endpoint(
    job_id: str,
    background_tasks: BackgroundTasks,
) -> RetryFailedResponse:
    try:
        retried_count, job = retry_failed_rows(job_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if retried_count > 0:
        processing_service = ProcessingService()
        worker = Worker(processing_service)
        background_tasks.add_task(worker.run_job, job_id)

    return RetryFailedResponse(
        retried_count=retried_count,
        message=f"{retried_count} failed row(s) requeued for processing",
    )


@router.get(
    "/jobs/{job_id}/download",
    responses={
        404: {"model": ErrorResponse, "description": "Job or output file not found"},
        409: {"model": ErrorResponse, "description": "No processed rows available yet"},
    },
)
async def download_job_output(job_id: str) -> FileResponse:
    job = repositories.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # If final output exists, use it (completed jobs)
    if job.output_file_path:
        safe_path = resolve_safe_output_path(job_id, job.output_file_path)
        if safe_path is None:
            raise HTTPException(status_code=404, detail="Output file not found")

        short_job_id = str(job.id)[:8]
        ext = ".xlsx" if job.input_format == "xlsx" else ".csv"
        download_name = f"enriched_{short_job_id}{ext}"

        return FileResponse(
            path=safe_path,
            filename=download_name,
            media_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                if job.input_format == "xlsx"
                else "text/csv"
            ),
        )

    # Otherwise, try to generate partial output
    from api.output_generator import generate_partial_output
    temp_path = generate_partial_output(job_id)
    if temp_path is None:
        raise HTTPException(status_code=409, detail="No processed rows available yet")

    short_job_id = str(job.id)[:8]
    ext = ".xlsx" if job.input_format == "xlsx" else ".csv"
    download_name = f"enriched_{short_job_id}{ext}"

    # Clean up temp file after response is sent
    def cleanup_temp_file():
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass

    return FileResponse(
        path=temp_path,
        filename=download_name,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if job.input_format == "xlsx"
            else "text/csv"
        ),
        background=BackgroundTask(lambda: temp_path.unlink(missing_ok=True)),
    )