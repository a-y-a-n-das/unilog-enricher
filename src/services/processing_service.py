from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Callable, TypeVar

from models.input_models import InputRecord
from pipeline.extraction.evidence import EvidenceBuilder
from pipeline.extraction.extraction import ProductExtractor
from pipeline.llm.factory import get_llm_client
from pipeline.research.agent import ResearchAgent

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True)
class ProcessingTimings:
    """Timing information for a single processed record."""

    research_seconds: float
    evidence_seconds: float
    extraction_seconds: float
    total_seconds: float


@dataclass(frozen=True)
class ProcessingResult:
    """Result of processing a single input record."""

    record: InputRecord
    product: object
    timings: ProcessingTimings


class ProcessingService:
    """
    Orchestrates the complete processing lifecycle for one InputRecord.

    Each recoverable pipeline stage can be retried independently.
    A failed stage does not cause previously completed stages to rerun.
    """

    def __init__(
        self,
        *,
        max_queries: int = 5,
        temp_root: Path | None = None,
        stage_retries: int = 3,
    ) -> None:
        self.max_queries = max_queries
        self.temp_root = temp_root
        self.stage_retries = stage_retries

        logger.info("Initializing processing service")

        start = perf_counter()

        self.llm = get_llm_client()

        logger.info(
            "LLM client initialized in %.2fs",
            perf_counter() - start,
        )

        self.research_agent = ResearchAgent(
            llm=self.llm,
        )

        self.evidence_builder = EvidenceBuilder()

        self.extractor = ProductExtractor(
            llm=self.llm,
            evidence_builder=self.evidence_builder,
        )

        logger.info("Processing service initialized")

    def process(
        self,
        record: InputRecord,
    ) -> ProcessingResult:
        """Process exactly one InputRecord."""

        total_start = perf_counter()

        logger.info(
            "[ROW %s] Starting processing",
            record.row_number,
        )

        with TemporaryDirectory(
            prefix=f"unilog-row-{record.row_number}-",
            dir=self.temp_root,
        ) as workspace:

            workspace_path = Path(workspace)

            logger.info(
                "[ROW %s] Temporary workspace: %s",
                record.row_number,
                workspace_path,
            )

            try:
                result = self._process_record(
                    record=record,
                    workspace=workspace_path,
                    total_start=total_start,
                )

                logger.info(
                    "[ROW %s] Processing completed successfully "
                    "in %.2fs",
                    record.row_number,
                    result.timings.total_seconds,
                )

                return result

            except Exception:
                logger.exception(
                    "[ROW %s] Processing failed",
                    record.row_number,
                )
                raise

    def _run_stage(
        self,
        *,
        stage_name: str,
        operation: Callable[[], T],
        retries: int | None = None,
    ) -> T:
        """
        Execute one pipeline stage with independent retries.

        Only the failing stage is repeated. Previously completed stages
        remain untouched.
        """

        max_attempts = retries or self.stage_retries
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(
                    "%s attempt %d/%d",
                    stage_name,
                    attempt,
                    max_attempts,
                )

                result = operation()

                logger.info(
                    "%s succeeded on attempt %d/%d",
                    stage_name,
                    attempt,
                    max_attempts,
                )

                return result

            except Exception as exc:
                last_error = exc

                logger.warning(
                    "%s failed on attempt %d/%d: %s",
                    stage_name,
                    attempt,
                    max_attempts,
                    exc,
                )

                if attempt < max_attempts:
                    logger.info(
                        "%s will be retried",
                        stage_name,
                    )

        raise RuntimeError(
            f"{stage_name} failed after {max_attempts} attempts"
        ) from last_error

    def _process_record(
        self,
        *,
        record: InputRecord,
        workspace: Path,
        total_start: float,
    ) -> ProcessingResult:

        # ---------------------------------------------------------
        # Research
        # ---------------------------------------------------------

        logger.info(
            "[ROW %s] Research started",
            record.row_number,
        )

        start = perf_counter()

        documents, research_usage = self._run_stage(
            stage_name=f"[ROW {record.row_number}] Research",
            operation=lambda: self.research_agent.run(
                record,
                max_queries=self.max_queries,
                workspace=workspace,
            ),
        )

        research_seconds = perf_counter() - start

        logger.info(
            "[ROW %s] Research completed: %d documents in %.2fs",
            record.row_number,
            len(documents),
            research_seconds,
        )

        # ---------------------------------------------------------
        # Evidence
        # ---------------------------------------------------------

        logger.info(
            "[ROW %s] Evidence building started",
            record.row_number,
        )

        start = perf_counter()

        evidence = self.evidence_builder.build(
            documents,
            record=record,
        )

        evidence_seconds = perf_counter() - start

        raw_research_chars = sum(
            len(document.content or "")
            for document in documents
        )

        logger.info(
            "[ROW %s] Evidence building completed in %.2fs "
            "(%d → %d chars)",
            record.row_number,
            evidence_seconds,
            raw_research_chars,
            len(evidence),
        )

        # ---------------------------------------------------------
        # Extraction
        # ---------------------------------------------------------

        logger.info(
            "[ROW %s] Extraction started",
            record.row_number,
        )

        start = perf_counter()

        extracted_product = self._run_stage(
            stage_name=f"[ROW {record.row_number}] Extraction",
            operation=lambda: self.extractor.extract(
                record=record,
                documents=documents,
            ),
        )

        extraction_seconds = perf_counter() - start

        logger.info(
            "[ROW %s] Extraction completed in %.2fs",
            record.row_number,
            extraction_seconds,
        )

        # ---------------------------------------------------------
        # Final result
        # ---------------------------------------------------------

        total_seconds = perf_counter() - total_start

        timings = ProcessingTimings(
            research_seconds=research_seconds,
            evidence_seconds=evidence_seconds,
            extraction_seconds=extraction_seconds,
            total_seconds=total_seconds,
        )

        return ProcessingResult(
            record=record,
            product=extracted_product,
            timings=timings,
        )