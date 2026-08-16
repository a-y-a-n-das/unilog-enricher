from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models import Job, JobRow

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def create_job(
    input_filename: str,
    input_format: str,
    total_rows: int,
    input_file_path: str,
) -> Job:
    with SessionLocal() as session:
        job = Job(
            input_filename=input_filename,
            input_format=input_format,
            total_rows=total_rows,
            input_file_path=input_file_path,
            status="queued",
            processed_rows=0,
            successful_rows=0,
            failed_rows=0,
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        return job


def create_job_rows(job_id: uuid.UUID, rows_data: list[dict]) -> list[JobRow]:
    with SessionLocal() as session:
        job_rows = [
            JobRow(
                job_id=job_id,
                row_number=row["row_number"],
                input_data=row["input_data"],
                status="pending",
                attempts=0,
            )
            for row in rows_data
        ]
        session.add_all(job_rows)
        session.commit()
        for row in job_rows:
            session.refresh(row)
        return job_rows


def create_job_with_rows(
    input_filename: str,
    input_format: str,
    total_rows: int,
    input_file_path: str,
    rows_data: list[dict],
) -> Job:
    with SessionLocal() as session:
        job = Job(
            input_filename=input_filename,
            input_format=input_format,
            total_rows=total_rows,
            input_file_path=input_file_path,
            status="queued",
            processed_rows=0,
            successful_rows=0,
            failed_rows=0,
        )
        session.add(job)
        session.flush()

        job_rows = [
            JobRow(
                job_id=job.id,
                row_number=row["row_number"],
                input_data=row["input_data"],
                status="pending",
                attempts=0,
            )
            for row in rows_data
        ]
        session.add_all(job_rows)

        session.commit()
        session.refresh(job)
        return job


def get_job(job_id: uuid.UUID) -> Job | None:
    with SessionLocal() as session:
        return session.get(Job, job_id)


def get_job_row(row_id: uuid.UUID) -> JobRow | None:
    with SessionLocal() as session:
        return session.get(JobRow, row_id)


def claim_next_pending_row(job_id: uuid.UUID | None = None) -> JobRow | None:
    with SessionLocal() as session:
        stmt = (
            select(JobRow)
            .where(JobRow.status == "pending")
            .order_by(JobRow.row_number)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job_id is not None:
            stmt = stmt.where(JobRow.job_id == job_id)

        row = session.execute(stmt).scalar_one_or_none()
        if row is None:
            return None

        row.status = "processing"
        row.attempts += 1
        row.started_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(row)
        return row


def mark_row_completed(
    row_id: uuid.UUID,
    result_data: dict,
    research_seconds: float,
    evidence_seconds: float,
    extraction_seconds: float,
    total_seconds: float,
) -> JobRow | None:
    with SessionLocal() as session:
        row = session.get(JobRow, row_id)
        if row is None:
            return None

        row.status = "completed"
        row.result_data = result_data
        row.research_seconds = research_seconds
        row.evidence_seconds = evidence_seconds
        row.extraction_seconds = extraction_seconds
        row.total_seconds = total_seconds
        row.completed_at = datetime.now(timezone.utc)
        row.error_message = None
        session.commit()
        session.refresh(row)
        return row


def mark_row_failed(row_id: uuid.UUID, error_message: str) -> JobRow | None:
    with SessionLocal() as session:
        row = session.get(JobRow, row_id)
        if row is None:
            return None

        row.status = "failed"
        row.error_message = error_message
        row.completed_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(row)
        return row


def update_job_progress(job_id: uuid.UUID) -> Job | None:
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if job is None:
            return None

        counts = session.execute(
            select(
                func.count(JobRow.id).label("total"),
                func.count(JobRow.id).filter(JobRow.status == "completed").label("successful"),
                func.count(JobRow.id).filter(JobRow.status == "failed").label("failed"),
                func.count(JobRow.id).filter(JobRow.status.in_(["completed", "failed"])).label("processed"),
            ).where(JobRow.job_id == job_id)
        ).one()

        job.total_rows = counts.total
        job.successful_rows = counts.successful
        job.failed_rows = counts.failed
        job.processed_rows = counts.processed

        session.commit()
        session.refresh(job)
        return job


def get_all_jobs() -> list[Job]:
    with SessionLocal() as session:
        stmt = select(Job).where(Job.job_type == "production").order_by(Job.created_at.desc())
        return session.execute(stmt).scalars().all()


def get_recoverable_jobs() -> list[Job]:
    """
    Get jobs that need recovery after a restart.

    Includes jobs with status 'queued' or 'processing' that have
    at least one row in 'pending' or 'processing' state.
    """
    with SessionLocal() as session:
        stmt = (
            select(Job)
            .where(Job.job_type == "production")
            .where(Job.status.in_(["queued", "processing"]))
            .where(
                select(JobRow.id)
                .where(JobRow.job_id == Job.id)
                .where(JobRow.status.in_(["pending", "processing"]))
                .exists()
            )
            .order_by(Job.created_at.desc())
        )
        return session.execute(stmt).scalars().all()


def reset_processing_rows(job_id: uuid.UUID) -> int:
    """
    Reset rows with status='processing' back to 'pending' for a job.

    Preserves the attempts count (does not decrement).
    Returns the number of rows reset.
    """
    with SessionLocal() as session:
        rows = session.execute(
            select(JobRow)
            .where(JobRow.job_id == job_id)
            .where(JobRow.status == "processing")
        ).scalars().all()

        count = 0
        for row in rows:
            row.status = "pending"
            row.started_at = None
            count += 1

        if count > 0:
            session.commit()

        return count


def reset_job_for_recovery(job_id: uuid.UUID) -> Job | None:
    """
    Reset a job to 'queued' status for recovery.

    Clears started_at so the job can be restarted fresh.
    Does not modify completed_at or error_message.
    """
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if job is None:
            return None

        job.status = "queued"
        job.started_at = None
        session.commit()
        session.refresh(job)
        return job