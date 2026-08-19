import logging
from time import perf_counter

from models.document_models import Document
from models.input_models import InputRecord
from models.research_models import SourceVerificationResult

from pipeline.ingestion.pdf_fetcher import Downloader
from pipeline.ingestion.pdf_parser import PDFParser
from pipeline.ingestion.resource_resolver import ResourceResolver
from pipeline.ingestion.web_scraper import WebScraper
from pipeline.llm.client import LLMClient
from pipeline.research.orchestrator import ResearchOrchestrator
from pipeline.research.query import generate_queries
from pipeline.research.search import (
    TavilySearch,
    deduplicate_results,
)
from pipeline.research.source_selector import select_sources
from pathlib import Path

MAX_OFFICIAL_PDFS = 5

LOGGER = logging.getLogger(__name__)


class _Timer:
    """Simple context manager for timing pipeline stages."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.start = 0.0

    def __enter__(self):
        self.start = perf_counter()
        return self

    def __exit__(self, *args):
        elapsed = perf_counter() - self.start

        LOGGER.info(
            "[TIME] %s: %.2fs",
            self.name,
            elapsed,
        )

        return False


class ResearchAgent:
    """
    Top-level first-pass research coordinator.

    Flow:

        InputRecord
            ↓
        Query Generator
            ↓
        Search
            ↓
        Source Selector
            ↓
        Research Orchestrator
            ↓
        Document[]
    """

    def __init__(
        self,
        llm: LLMClient,
        searcher: TavilySearch | None = None,
        orchestrator: ResearchOrchestrator | None = None,
    ) -> None:
        self.llm = llm

        self.searcher = (
            searcher
            or TavilySearch()
        )

        self.orchestrator = (
            orchestrator
            or ResearchOrchestrator(
                scraper=WebScraper(),
                downloader=Downloader(),
                pdf_parser=PDFParser(),
                resource_resolver=ResourceResolver(),
            )
        )

    def run(
        self,
        record: InputRecord,
        max_queries: int | None = None,
        workspace: Path | None = None,
    ) -> list[Document]:
        """
        Run the complete first-pass research pipeline.

        This currently performs:
        - query generation
        - search
        - source selection
        - document collection

        Follow-up/deep-research iterations are intentionally
        not included yet.
        """

        LOGGER.info(
            "[Research] Starting row %s",
            record.row_number,
        )

        # -----------------------------------------------------
        # 1. Query generation
        # -----------------------------------------------------
        with _Timer("Query generation"):
            queries = generate_queries(
                record=record,
                llm=self.llm,
                max_queries=max_queries,
            )

        LOGGER.info(
            "[Research] Generated %d queries",
            len(queries),
        )

        for index, query in enumerate(
            queries,
            start=1,
        ):
            LOGGER.info(
                "[Research] Query %d: %s",
                index,
                query,
            )

        if not queries:
            LOGGER.warning(
                "[Research] No queries generated"
            )
            return []

        # -----------------------------------------------------
        # 2. Search
        # -----------------------------------------------------
        all_results = []

        for query in queries:
            LOGGER.info(
                "[Research] Searching: %s",
                query,
            )

            with _Timer(f"Search: {query}"):
                results = self.searcher.search(query)

            LOGGER.info(
                "[Research] Search returned %d results",
                len(results),
            )

            all_results.extend(results)

        # -----------------------------------------------------
        # 3. Deduplicate search results
        # -----------------------------------------------------
        results = deduplicate_results(
            all_results
        )

        LOGGER.info(
            "[Research] Search results: %d → %d unique",
            len(all_results),
            len(results),
        )

        if not results:
            LOGGER.warning(
                "[Research] No search results available"
            )
            return []

        # -----------------------------------------------------
        # 4. Source selection
        # -----------------------------------------------------
        with _Timer("Source selection"):
            selected_sources: SourceVerificationResult = (
                select_sources(
                    record=record,
                    results=results,
                    llm=self.llm,
                )
            )

        ingestible_sources = [
            source
            for source in selected_sources.sources
            if source.should_ingest
        ]

        official_pdf_count = 0
        limited_sources = []

        for source in ingestible_sources:
            if source.source_type == "pdf":
                if official_pdf_count >= MAX_OFFICIAL_PDFS:
                    LOGGER.info(
                        "[Research] Skipping official PDF "
                        "(5 PDF limit reached): %s",
                        source.url,
                    )
                    continue

                official_pdf_count += 1

            limited_sources.append(source)

        ingestible_sources = limited_sources

        LOGGER.info(
            "[Research] Source selector returned %d sources",
            len(selected_sources.sources),
        )

        LOGGER.info(
            "[Research] %d sources selected for ingestion",
            len(ingestible_sources),
        )

        for source in ingestible_sources:
            LOGGER.info(
                "[Research] Selected source: %s",
                source.url,
            )

        if not ingestible_sources:
            LOGGER.warning(
                "[Research] No sources selected for ingestion"
            )
            return []

        # -----------------------------------------------------
        # 5. Document collection
        # -----------------------------------------------------
        with _Timer("Document collection"):
            documents = self.orchestrator.collect(
            SourceVerificationResult(
                sources=ingestible_sources
            ),
            workspace=workspace,
        )
        LOGGER.info(
            "[Research] Collected %d documents",
            len(documents),

        )

        return documents