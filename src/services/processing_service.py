from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from models.input_models import InputRecord
from pipeline.extraction.evidence import EvidenceBuilder
from pipeline.extraction.extraction import ProductExtractor
from pipeline.llm.factory import get_llm_client
from pipeline.research.agent import ResearchAgent


logger = logging.getLogger(__name__)


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

    Responsibilities:
        - initialize shared pipeline dependencies
        - create an isolated temporary workspace for the record
        - run research
        - build evidence
        - run extraction
        - return the final result
        - guarantee temporary workspace cleanup

    This class intentionally does NOT contain the research or extraction
    business logic. Those responsibilities remain inside the existing
    pipeline components.
    """

    def __init__(
        self,
        *,
        max_queries: int = 5,
        temp_root: Path | None = None,
    ) -> None:
        self.max_queries = max_queries
        self.temp_root = temp_root

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
        """
        Process exactly one InputRecord.

        A dedicated temporary workspace is created for this record and
        guaranteed to be removed when processing finishes, regardless of
        success or failure.

        Raises:
            Exception: Any exception from the underlying pipeline is allowed
                to propagate to the caller. The workspace cleanup still
                occurs because it is handled by the context manager.
        """

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

    def _process_record(
        self,
        *,
        record: InputRecord,
        workspace: Path,
        total_start: float,
    ) -> ProcessingResult:
        """
        Execute the actual single-record pipeline.
        """

        # ---------------------------------------------------------
        # Research
        # ---------------------------------------------------------

        logger.info(
            "[ROW %s] Research started",
            record.row_number,
        )

        start = perf_counter()

        documents = self.research_agent.run(
            record,
            max_queries=self.max_queries,
            workspace=workspace,
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

        extracted_product = self.extractor.extract(
            record=record,
            documents=documents,
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

