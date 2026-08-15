from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from database import repositories
from database.models import Job
from models.input_models import InputRecord
from pipeline.llm.config import get_worker_concurrency
from services.processing_service import ProcessingResult, ProcessingService

if TYPE_CHECKING:
    from database.models import JobRow

logger = logging.getLogger(__name__)


class Worker:
    """
    Worker that processes all pending rows for a single job.

    Uses a fixed thread pool (WORKER_CONCURRENCY) where each thread
    repeatedly claims and processes rows until none remain.
    """

    def __init__(
        self,
        processing_service: ProcessingService,
    ) -> None:
        self.processing_service = processing_service

    def run_job(self, job_id: str) -> None:
        """
        Process all pending rows for the given job.

        Transitions the job from queued to processing, processes each row
        using a thread pool, and completes the job when all rows reach terminal states.
        """
        job = repositories.get_job(job_id)
        if job is None:
            logger.warning("[JOB %s] Job not found", job_id)
            return

        if job.status == "completed":
            logger.info("[JOB %s] Job already completed", job_id)
            return

        if job.status == "failed":
            logger.info("[JOB %s] Job already failed", job_id)
            return

        if job.status == "queued":
            logger.info("[JOB %s] Transitioning job from queued to processing", job_id)
            job.status = "processing"
            job.started_at = self._now_utc()
            with repositories.SessionLocal() as session:
                session.add(job)
                session.commit()

        logger.info("[JOB %s] Worker started", job_id)

        concurrency = get_worker_concurrency()
        if concurrency == 1:
            self._run_sequential(job_id)
        else:
            self._run_concurrent(job_id, concurrency)

        final_job = repositories.update_job_progress(job_id)
        if final_job and final_job.processed_rows == final_job.total_rows:
            final_job.status = "completed"
            final_job.completed_at = self._now_utc()
            with repositories.SessionLocal() as session:
                session.add(final_job)
                session.commit()
            logger.info("[JOB %s] Job completed", job_id)

            from api.output_generator import generate_output
            generate_output(job_id)
            logger.info("[JOB %s] Output generated", job_id)
        else:
            logger.info("[JOB %s] Worker finished (pending rows remain)", job_id)

    def _run_sequential(self, job_id: str) -> None:
        """Sequential processing (WORKER_CONCURRENCY=1)."""
        while True:
            row = repositories.claim_next_pending_row(job_id)
            if row is None:
                break
            self._process_row(job_id, row)

    def _run_concurrent(self, job_id: str, concurrency: int) -> None:
        """Concurrent processing using a fixed thread pool."""
        logger.info("[JOB %s] Starting %d concurrent workers", job_id, concurrency)

        def worker_loop() -> None:
            while True:
                row = repositories.claim_next_pending_row(job_id)
                if row is None:
                    break
                self._process_row(job_id, row)

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(worker_loop) for _ in range(concurrency)]
            for future in futures:
                future.result()

    def _process_row(self, job_id: str, row: "JobRow") -> None:
        """
        Process a single claimed row.

        Converts stored input_data to InputRecord, calls ProcessingService,
        and persists the result or failure.
        """
        logger.info("[JOB %s] Claimed row %s", job_id, row.row_number)

        record = self._convert_to_input_record(row)
        if record is None:
            logger.error("[JOB %s] Row %s: failed to convert input_data", job_id, row.row_number)
            repositories.mark_row_failed(row.id, "Failed to convert input_data to InputRecord")
            repositories.update_job_progress(job_id)
            return

        try:
            result = self.processing_service.process(record)
            self._handle_success(job_id, row, result)
        except Exception as e:
            self._handle_failure(job_id, row, e)

        repositories.update_job_progress(job_id)

    def _convert_to_input_record(self, row: "JobRow") -> InputRecord | None:
        """
        Convert JobRow.input_data to InputRecord.

        Preserves the original row_number and data.
        """
        try:
            input_data = row.input_data
            row_number = row.row_number
            data = input_data.get("data", input_data)

            return InputRecord(row_number=row_number, data=data)
        except Exception:
            logger.exception("[JOB %s] Row %s: conversion failed", row.job_id, row.row_number)
            return None

    def _handle_success(
        self,
        job_id: str,
        row: "JobRow",
        result: ProcessingResult,
    ) -> None:
        """
        Persist successful processing result.
        """
        timings = result.timings
        product_data = self._make_json_serializable(result.product)

        repositories.mark_row_completed(
            row_id=row.id,
            result_data=product_data,
            research_seconds=timings.research_seconds,
            evidence_seconds=timings.evidence_seconds,
            extraction_seconds=timings.extraction_seconds,
            total_seconds=timings.total_seconds,
        )
        logger.info("[JOB %s] Row %s completed", job_id, row.row_number)

    def _handle_failure(self, job_id: str, row: "JobRow", error: Exception) -> None:
        """
        Persist row failure.
        """
        error_message = f"{type(error).__name__}: {error}"
        repositories.mark_row_failed(row.id, error_message)
        logger.error("[JOB %s] Row %s failed: %s", job_id, row.row_number, error_message)

    def _make_json_serializable(self, obj: object) -> dict:
        """
        Convert product object to JSON-serializable dict.
        """
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "dict"):
            return obj.dict()
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return {"value": str(obj)}

    def _now_utc(self):
        from datetime import datetime, timezone
        return datetime.now(timezone.utc)