from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class JobCreateResponse(BaseModel):
    job_id: str
    status: str
    total_rows: int


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    input_filename: str
    input_format: str
    total_rows: int
    processed_rows: int
    successful_rows: int
    failed_rows: int
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    output_available: bool = False
    job_type: str = "production"


class JobRowResponse(BaseModel):
    row_number: int
    status: str
    attempts: int
    error_message: str | None = None
    completed_at: datetime | None = None


class JobListResponse(BaseModel):
    jobs: list[JobStatusResponse]


class ErrorResponse(BaseModel):
    detail: str


class RetryFailedResponse(BaseModel):
    retried_count: int
    message: str


class TavilyUsageResponse(BaseModel):
    rows_processed_this_session: int
    estimated_rows_remaining: int
    max_rows_per_month: int
    estimated_credits_per_row: int
    monthly_credit_limit: int
    note: str


def make_job_status_response(job) -> JobStatusResponse:
    return JobStatusResponse(
        job_id=str(job.id),
        status=job.status,
        input_filename=job.input_filename,
        input_format=job.input_format,
        total_rows=job.total_rows,
        processed_rows=job.processed_rows,
        successful_rows=job.successful_rows,
        failed_rows=job.failed_rows,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        output_available=job.output_file_path is not None,
        job_type=job.job_type,
    )


def make_job_row_response(row) -> JobRowResponse:
    return JobRowResponse(
        row_number=row.row_number,
        status=row.status,
        attempts=row.attempts,
        error_message=row.error_message,
        completed_at=row.completed_at,
    )