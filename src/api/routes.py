from __future__ import annotations

import logging
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
from api.models import (
    CreditsResponse,
    ErrorResponse,
    JobCreateResponse,
    JobListResponse,
    JobRowResponse,
    JobStatusResponse,
    RetryFailedResponse,
)
from api.storage import save_upload_file
from api.output_generator import generate_output, generate_partial_output
from database import repositories
from database.models import Job
from models.input_models import InputRecord
from pipeline.input.csv import load_input_csv
from pipeline.input.xlsx import load_input_xlsx
from services.free_credits import get_free_credits_tracker
from services.job_service import ValidationError, create_job, get_job_status, retry_failed_rows
from services.processing_service import ProcessingService
from services.worker import Worker

if TYPE_CHECKING:
    from database.models import JobRow

router = APIRouter()
logger = logging.getLogger(__name__)


def get_processing_service() -> ProcessingService:
    return ProcessingService()


def get_free_credits_tracker_dependency():
    """Dependency to get the global free credits tracker."""
    from services.free_credits import get_free_credits_tracker
    return get_free_credits_tracker()


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

    # Refresh job progress so counts reflect requeued rows immediately
    if retried_count > 0:
        repositories.update_job_progress(job_id)

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

    output_path = generate_output(job_id)
    if output_path is None or not output_path.exists():
        from api.output_generator import generate_partial_output
        output_path = generate_partial_output(job_id)
    if output_path is None or not output_path.exists():
        raise HTTPException(status_code=409, detail="No processed rows available yet")

    short_job_id = str(job.id)[:8]
    return FileResponse(
        path=output_path,
        filename=f"enriched_{short_job_id}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get(
    "/credits",
    response_model=CreditsResponse,
    responses={
        500: {"model": ErrorResponse, "description": "Failed to retrieve credits information"},
    },
)
async def get_credits(
    tracker=Depends(get_free_credits_tracker_dependency),
) -> CreditsResponse:
    """Get remaining free credits for row processing.

    Each attempted row consumes 1 credit, regardless of outcome.
    This is an application-level allowance, not related to Exa API billing.
    """
    try:
        summary = tracker.get_summary()
        return CreditsResponse(
            remaining_credits=summary.remaining_credits,
            initial_credits=summary.initial_credits,
            credits_used_this_session=summary.credits_used_this_session,
            note=summary.note,
        )
    except Exception as e:
        logger.exception("Failed to retrieve credits")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve credits information",
        )