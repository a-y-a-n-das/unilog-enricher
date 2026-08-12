import logging
from urllib.parse import urlparse, urlunparse

from models.document_models import Document
from models.research_models import SourceVerificationResult
from pipeline.ingestion.pdf_fetcher import Downloader
from pipeline.ingestion.pdf_parser import PDFParser
from pipeline.ingestion.web_scraper import WebScraper
from pipeline.ingestion.resource_resolver import ResourceResolver

LOGGER = logging.getLogger(__name__)


class ResearchOrchestrator:
    """
    Convert source-selector results into a canonical document collection.

    Rules:
    - Direct PDF sources are downloaded and parsed.
    - Webpage sources are scraped into a Document.
    - Only immediate PDF links discovered on webpages are followed.
    - Non-PDF sub-links are never followed.
    - Documents are deduplicated by normalized URL.
    """

    def __init__(
        self,
        scraper: WebScraper,
        downloader: Downloader,
        pdf_parser: PDFParser,
        resource_resolver: ResourceResolver,
    ) -> None:
        self.scraper = scraper
        self.downloader = downloader
        self.pdf_parser = pdf_parser
        self.resource_resolver = resource_resolver

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Normalize a URL for deduplication."""

        parsed = urlparse(url.strip())

        # Fragments do not identify a different document.
        parsed = parsed._replace(fragment="")

        return urlunparse(parsed)

    def _add_document(
        self,
        documents: list[Document],
        seen_urls: set[str],
        document: Document,
    ) -> None:
        """Add a document once, based on its normalized source URL."""

        url = document.metadata.get("url")

        if not url:
            LOGGER.warning(
                "[Orchestrator] Skipping document without URL"
            )
            return

        normalized_url = self._normalize_url(url)

        if normalized_url in seen_urls:
            LOGGER.debug(
                "[Orchestrator] Skipping duplicate document: %s",
                url,
            )
            return

        seen_urls.add(normalized_url)
        documents.append(document)

    def _parse_pdf(
        self,
        url: str,
        source_url: str,
    ) -> Document:
        """
        Download and parse a PDF URL.

        source_url identifies where the PDF came from:
        - direct selected PDF: source_url == url
        - discovered PDF: source_url == parent webpage
        """

        LOGGER.info(
            "[Orchestrator] Downloading PDF: %s",
            url,
        )

        pdf_path = self.downloader.download(url)

        LOGGER.info(
            "[Orchestrator] Parsing PDF: %s",
            pdf_path,
        )

        document = self.pdf_parser.parse(pdf_path)

        metadata = dict(document.metadata or {})

        metadata["url"] = url
        metadata["source_url"] = source_url
        metadata["document_type"] = "pdf"

        return document.model_copy(
            update={
                "metadata": metadata,
            }
        )

    def _process_webpage(
        self,
        url: str,
        documents: list[Document],
        seen_urls: set[str],
    ) -> None:
        """
        Scrape one webpage.

        The webpage itself becomes a Document.

        ResourceResolver handles:
        - URL filtering
        - irrelevant URL filtering
        - direct PDF detection
        - document-looking URL detection
        - parallel PDF verification
        - PDF downloading
        - PDF parsing

        Only immediate PDF links are resolved.
        No non-PDF webpage links are followed.
        """

        LOGGER.info(
            "[Orchestrator] Scraping webpage: %s",
            url,
        )

        page = self.scraper.scrape(url)

        metadata = dict(page.metadata or {})

        metadata["url"] = url
        metadata["source_url"] = url
        metadata["document_type"] = "webpage"

        page = page.model_copy(
            update={
                "metadata": metadata,
            }
        )

        self._add_document(
            documents,
            seen_urls,
            page,
        )

        LOGGER.info(
            "[Orchestrator] Webpage produced %d links",
            len(page.links),
        )

        # ---------------------------------------------------------
        # Resolve ONLY PDF links from this webpage.
        #
        # ResourceResolver performs the existing filtering before
        # any expensive PDF detection.
        # ---------------------------------------------------------
        resolver_seen_urls = set(seen_urls)

        pdf_documents = (
            self.resource_resolver.resolve_pdf_links(
                links=page.links,
                source_url=url,
                seen_urls=resolver_seen_urls,
            )
        )

        LOGGER.info(
            "[Orchestrator] Resolver returned %d PDF documents",
            len(pdf_documents),
        )


        for pdf_document in pdf_documents:
            self._add_document(
                documents,
                seen_urls,
                pdf_document,
            )

    def collect(
        self,
        sources: SourceVerificationResult,
    ) -> list[Document]:
        """
        Collect Documents from selected sources.

        No LLM calls are made here.

        Webpage expansion is exactly one level deep:
            webpage -> immediate PDF links

        Non-PDF sub-links are never followed.
        """

        documents: list[Document] = []
        seen_urls: set[str] = set()

        selected_sources = [
            source
            for source in sources.sources
            if source.should_ingest
        ]

        LOGGER.info(
            "[Orchestrator] Processing %d selected sources",
            len(selected_sources),
        )

        for source in selected_sources:
            url = self._normalize_url(source.url)

            if not url:
                continue

            if url in seen_urls:
                LOGGER.debug(
                    "[Orchestrator] Duplicate source: %s",
                    url,
                )
                continue

            try:
                # -------------------------------------------------
                # Direct PDF source
                # -------------------------------------------------
                if self.downloader.is_pdf(url):
                    LOGGER.info(
                        "[Orchestrator] Processing direct PDF: %s",
                        url,
                    )

                    document = self._parse_pdf(
                        url=url,
                        source_url=url,
                    )

                    self._add_document(
                        documents,
                        seen_urls,
                        document,
                    )

                # -------------------------------------------------
                # Webpage source
                # -------------------------------------------------
                else:
                    self._process_webpage(
                        url=url,
                        documents=documents,
                        seen_urls=seen_urls,
                    )

            except Exception:
                LOGGER.exception(
                    "[Orchestrator] Failed to process source: %s",
                    url,
                )

        LOGGER.info(
            "[Orchestrator] Produced %d documents",
            len(documents),
        )

        return documents