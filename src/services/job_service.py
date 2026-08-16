from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from models.input_models import InputRecord
from database import repositories
from database.models import Job, JobRow

if TYPE_CHECKING:
    from database.models import Job, JobRow


@dataclass(frozen=True)
class JobStatus:
    job_id: str
    status: str
    total_rows: int
    processed_rows: int
    successful_rows: int
    failed_rows: int


class ValidationError(ValueError):
    pass


def validate_rows(rows: list[InputRecord]) -> None:
    if not rows:
        raise ValidationError("At least one input row is required")

    seen_numbers: set[int] = set()
    for row in rows:
        if row.row_number in seen_numbers:
            raise ValidationError(f"Duplicate row number: {row.row_number}")
        seen_numbers.add(row.row_number)


def validate_input_format(input_format: str) -> None:
    valid_formats = {"csv", "xlsx", "jsonl"}
    if input_format not in valid_formats:
        raise ValidationError(
            f"Invalid input format: {input_format}. Valid formats: {valid_formats}"
        )


def create_job(
    input_filename: str,
    input_format: str,
    input_file_path: str,
    rows: list[InputRecord],
) -> Job:
    validate_input_format(input_format)
    validate_rows(rows)

    total_rows = len(rows)

    rows_data = [
        {"row_number": row.row_number, "input_data": row.data}
        for row in rows
    ]

    job = repositories.create_job_with_rows(
        input_filename=input_filename,
        input_format=input_format,
        total_rows=total_rows,
        input_file_path=input_file_path,
        rows_data=rows_data,
    )

    return job


def get_job_status(job_id: str) -> JobStatus | None:
    job = repositories.get_job(job_id)
    if job is None:
        return None

    return JobStatus(
        job_id=str(job.id),
        status=job.status,
        total_rows=job.total_rows,
        processed_rows=job.processed_rows,
        successful_rows=job.successful_rows,
        failed_rows=job.failed_rows,
    )


def retry_failed_rows(job_id: str) -> tuple[int, Job | None]:
    job = repositories.get_job(job_id)
    if job is None:
        raise ValueError("Job not found")
    return repositories.requeue_failed_rows(job.id)