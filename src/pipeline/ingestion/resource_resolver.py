import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urlunparse

from models.document_models import Document
from pipeline.ingestion.pdf_fetcher import Downloader
from pipeline.ingestion.pdf_parser import PDFParser
from pipeline.ingestion.web_scraper import WebScraper
from pathlib import Path

LOGGER = logging.getLogger(__name__)


class ResourceResolver:
    PDF_CHECK_WORKERS = 8
    WEB_SCRAPE_WORKERS = 5

    # Maximum number of PDFs that may be processed from one
    # resource-resolution pass.
    MAX_PDF_RESOURCES = 5

    LANGUAGE_CODES = {
        "en", "fr", "es", "de", "it", "pt", "nl", "da", "sv", "no",
        "fi", "pl", "cs", "sk", "hu", "ro", "ru", "uk", "tr", "el",
        "ja", "ko", "zh", "ar", "he", "hi", "th", "vi", "id", "ms",
    }

    LANGUAGE_PRIORITY = {
        "en": 0, "fr": 1, "es": 2, "de": 3, "it": 4, "pt": 5, "nl": 6,
        "da": 7, "sv": 8, "no": 9, "fi": 10, "pl": 11, "cs": 12,
        "sk": 13, "hu": 14, "ro": 15, "ru": 16, "uk": 17, "tr": 18,
        "el": 19, "ja": 20, "ko": 21, "zh": 22, "ar": 23, "he": 24,
        "hi": 25, "th": 26, "vi": 27, "id": 28, "ms": 29,
    }

    def __init__(
        self,
        max_resources: int = 50,
        max_webpages: int = 5,
        downloader: Downloader | None = None,
        pdf_parser: PDFParser | None = None,
        web_scraper: WebScraper | None = None,
    ) -> None:
        self.downloader = downloader or Downloader()
        self.pdf_parser = pdf_parser or PDFParser()
        self.web_scraper = web_scraper or WebScraper()

        # Overall resource limit.
        self.max_resources = max_resources

        # Maximum webpages to scrape.
        self.max_webpages = max_webpages

    def resolve(
        self,
        document: Document,
        product: str | None = None,
        target_terms: list[str] | None = None,
        workspace: Path | None = None,
    ) -> list[Document]:
        """
        Resolve useful resources discovered in a document.

        Filtering and ranking are deterministic.
        Semantic relevance decisions remain with the LLM source selector.
        """

        return self._resolve_links(
            document.links,
            seen_urls=set(),
            target_terms=target_terms,
            workspace=workspace,
        )

    def resolve_pdf_links(
        self,
        links: list[str],
        source_url: str | None = None,
        seen_urls: set[str] | None = None,
        max_resources: int | None = None,
        workspace: Path | None = None,
    ) -> tuple[list[Document], set[str]]:
        """
        Resolve only PDF resources from a set of links.

        This performs exactly one level of expansion:

            webpage
                -> immediate links
                -> PDF links only
                -> PDF documents

        Non-PDF webpages are ignored and never scraped.

        PDF processing is limited independently from the overall
        resource limit.

        Filtering remains deterministic and zero-network until
        document-looking URLs reach PDF detection.
        """

        if seen_urls is None:
            seen_urls = set()

        if max_resources is None:
            max_resources = self.MAX_PDF_RESOURCES

        # Never allow this method to exceed the global PDF cap.
        max_resources = min(
            max_resources,
            self.MAX_PDF_RESOURCES,
        )

        possible_pdf_urls: list[str] = []
        pdf_urls: list[str] = []

        # =============================================================
        # Stage 1: Cheap, zero-network filtering
        # =============================================================
        for link in links:
            if len(pdf_urls) >= max_resources:
                LOGGER.info(
                    "[Resolver] PDF resource limit reached: %d",
                    max_resources,
                )
                break

            url = self._normalize_url(link)

            if not self._is_supported_url(url):
                continue

            if not self._is_relevant_url(url):
                LOGGER.info(
                    "[Resolver] Skipping irrelevant URL: %s",
                    url,
                )
                continue

            if url in seen_urls:
                continue

            seen_urls.add(url)

            # ---------------------------------------------------------
            # Explicit PDF URL.
            # ---------------------------------------------------------
            if self._is_pdf_url(url):
                LOGGER.info(
                    "[Resolver] PDF link: %s",
                    url,
                )

                pdf_urls.append(url)
                continue

            # ---------------------------------------------------------
            # Only document-looking URLs reach network PDF detection.
            # ---------------------------------------------------------
            if self._looks_like_document_url(url):
                possible_pdf_urls.append(url)

        # =============================================================
        # Stage 2: Parallel PDF detection
        # =============================================================

        remaining_capacity = (
            max_resources - len(pdf_urls)
        )

        if remaining_capacity > 0:
            candidates_to_check = possible_pdf_urls[
                :remaining_capacity
            ]

            detected_pdf_urls = self._detect_pdfs_parallel(
                candidates_to_check
            )

            for url in detected_pdf_urls:
                if url not in pdf_urls:
                    pdf_urls.append(url)

        # =============================================================
        # Stage 2.5: Deduplicate obvious language variants before the
        # PDF limit is applied.
        # =============================================================
        before_dedup = len(pdf_urls)
        pdf_urls = self._deduplicate_language_variants(pdf_urls)

        if len(pdf_urls) != before_dedup:
            LOGGER.info(
                "[Resolver] Language-variant deduplication: %d -> %d PDFs",
                before_dedup,
                len(pdf_urls),
            )

        # Hard PDF limit.
        pdf_urls = pdf_urls[:max_resources]

        # =============================================================
        # Stage 3: Download + parse PDFs
        # =============================================================
        documents: list[Document] = []

        for url in pdf_urls:
            LOGGER.info(
                "[Resolver] Processing PDF: %s",
                url,
            )

            document = self._process_pdf(
                url,
                source_url=source_url,
                workspace=workspace,
            )

            if document is not None:
                documents.append(document)

        LOGGER.info(
            "[Resolver] Resolved %d PDF documents from %d links",
            len(documents),
            len(links),
        )

        return documents, set(pdf_urls)

    def _resolve_links(
        self,
        links: list[str],
        seen_urls: set[str] | None = None,
        target_terms: list[str] | None = None,
        max_resources: int | None = None,
        workspace: Path | None = None,
    ) -> list[Document]:
        """
        Resolve both PDF and webpage resources.

        Overall resource limit:
            max_resources

        Independent PDF limit:
            MAX_PDF_RESOURCES

        Independent webpage limit:
            max_webpages
        """

        if seen_urls is None:
            seen_urls = set()

        if max_resources is None:
            max_resources = self.max_resources

        documents: list[Document] = []
        webpage_candidates: list[str] = []
        possible_pdf_urls: list[str] = []

        # =============================================================
        # Stage 1: Cheap, zero-network filtering
        # =============================================================
        for link in links:
            if len(documents) >= max_resources:
                LOGGER.info(
                    "[Resolver] Resource limit reached: %d",
                    max_resources,
                )
                break

            url = self._normalize_url(link)

            if not self._is_supported_url(url):
                continue

            if not self._is_relevant_url(url):
                LOGGER.info(
                    "[Resolver] Skipping irrelevant URL: %s",
                    url,
                )
                continue

            if url in seen_urls:
                continue

            seen_urls.add(url)

            # ---------------------------------------------------------
            # Explicit PDF URL: no network detection required.
            # ---------------------------------------------------------
            if self._is_pdf_url(url):
                documents.append(
                    ("pdf", url)
                )
                continue

            # ---------------------------------------------------------
            # Only URLs that look like documents get an expensive
            # network-based PDF check.
            # ---------------------------------------------------------
            if self._looks_like_document_url(url):
                possible_pdf_urls.append(url)
            else:
                webpage_candidates.append(url)

        # =============================================================
        # Stage 2: PDF detection
        # =============================================================

        # Explicit PDFs found during cheap URL filtering.
        pdf_urls = [
            url
            for kind, url in documents
            if kind == "pdf"
        ]

        # Never process more than MAX_PDF_RESOURCES PDFs.
        pdf_urls = pdf_urls[
            :self.MAX_PDF_RESOURCES
        ]

        remaining_pdf_capacity = (
            self.MAX_PDF_RESOURCES - len(pdf_urls)
        )

        # Only perform network PDF detection for enough candidates
        # to fill the remaining PDF capacity.
        if remaining_pdf_capacity > 0:
            candidates_to_check = possible_pdf_urls[
                :remaining_pdf_capacity
            ]

            detected_pdf_urls = self._detect_pdfs_parallel(
                candidates_to_check
            )

            for url in detected_pdf_urls:
                if url not in pdf_urls:
                    pdf_urls.append(url)

        # =============================================================
        # Deduplicate obvious language variants before applying the
        # final PDF resource limit.
        # =============================================================
        before_dedup = len(pdf_urls)
        pdf_urls = self._deduplicate_language_variants(pdf_urls)

        if len(pdf_urls) != before_dedup:
            LOGGER.info(
                "[Resolver] Language-variant deduplication: %d -> %d PDFs",
                before_dedup,
                len(pdf_urls),
            )

        # Final hard PDF limit.
        pdf_urls = pdf_urls[
            :self.MAX_PDF_RESOURCES
        ]

        # Replace temporary tuples with actual documents.
        documents = []

        # =============================================================
        # Stage 3: Process PDFs
        #
        # Keep parsing sequential for now because PDF parsing may
        # invoke OCR and can be CPU/memory intensive.
        # =============================================================
        for url in pdf_urls:
            if len(documents) >= max_resources:
                break

            LOGGER.info(
                "[Resolver] Processing PDF: %s",
                url,
            )

            document = self._process_pdf(
                url,
                workspace=workspace,
            )

            if document is not None:
                documents.append(document)

        # =============================================================
        # Stage 4: Rank webpages locally
        #
        # No network requests here.
        # =============================================================
        selected_webpages = self._select_webpage_candidates(
            webpage_candidates,
            target_terms=target_terms,
        )

        # Respect overall resource limit.
        remaining_capacity = (
            max_resources - len(documents)
        )

        if remaining_capacity <= 0:
            return documents

        selected_webpages = selected_webpages[
            :min(
                self.max_webpages,
                remaining_capacity,
            )
        ]

        # =============================================================
        # Stage 5: Parallel webpage scraping
        # =============================================================
        webpage_documents = self._scrape_webpages_parallel(
            selected_webpages
        )

        documents.extend(
            webpage_documents
        )

        return documents[:max_resources]

    def _detect_pdfs_parallel(
        self,
        urls: list[str],
    ) -> list[str]:
        """
        Determine which document-looking URLs are PDFs.

        is_pdf() performs network I/O, so it is safe and useful to
        parallelize with a bounded thread pool.
        """

        if not urls:
            return []

        detected: list[str] = []

        LOGGER.info(
            "[Resolver] Checking %d possible document URLs for PDFs",
            len(urls),
        )

        with ThreadPoolExecutor(
            max_workers=self.PDF_CHECK_WORKERS
        ) as executor:
            future_to_url = {
                executor.submit(
                    self.downloader.is_pdf,
                    url,
                ): url
                for url in urls
            }

            for future in as_completed(
                future_to_url
            ):
                url = future_to_url[
                    future
                ]

                try:
                    if future.result():
                        detected.append(url)

                except Exception as exc:
                    LOGGER.warning(
                        "[Resolver] PDF detection failed for %s: %s",
                        url,
                        exc,
                    )

        return detected

    def _scrape_webpages_parallel(
        self,
        urls: list[str],
    ) -> list[Document]:
        """
        Scrape selected webpages concurrently.

        Web scraping is I/O-bound, so a small thread pool is appropriate.
        """

        if not urls:
            return []

        documents_by_url: dict[
            str,
            Document,
        ] = {}

        LOGGER.info(
            "[Resolver] Scraping %d selected webpages in parallel",
            len(urls),
        )

        with ThreadPoolExecutor(
            max_workers=min(
                self.WEB_SCRAPE_WORKERS,
                len(urls),
            )
        ) as executor:
            future_to_url = {
                executor.submit(
                    self.web_scraper.scrape,
                    url,
                ): url
                for url in urls
            }

            for future in as_completed(
                future_to_url
            ):
                url = future_to_url[
                    future
                ]

                try:
                    document = future.result()

                    document.metadata.setdefault(
                        "url",
                        url,
                    )

                    documents_by_url[
                        url
                    ] = document

                except Exception as exc:
                    LOGGER.warning(
                        "[Resolver] Failed to process webpage %s: %s",
                        url,
                        exc,
                    )

        # Preserve the ranking order rather than completion order.
        return [
            documents_by_url[url]
            for url in urls
            if url in documents_by_url
        ]

    def _process_pdf(
        self,
        url: str,
        source_url: str | None = None,
        workspace: Path | None = None,
    ) -> Document | None:
        try:
            pdf_path = self.downloader.download(
                url,
                workspace=workspace
            )

            document = self.pdf_parser.parse(
                pdf_path
            )

            document.metadata.setdefault(
                "url",
                url,
            )

            if source_url:
                document.metadata[
                    "source_url"
                ] = source_url

            document.metadata[
                "document_type"
            ] = "pdf"

            return document

        except Exception as exc:
            LOGGER.warning(
                "[Resolver] Failed to process PDF %s: %s",
                url,
                exc,
            )

            return None

    def _select_webpage_candidates(
        self,
        urls: list[str],
        target_terms: list[str] | None = None,
    ) -> list[str]:
        """
        Rank webpage candidates using deterministic signals.

        Priority:
            1. Target-specific terminology
            2. Technical/document/resource terminology
            3. Product/specification-related paths
            4. Generic product pages
        """

        scored: list[
            tuple[int, str, str]
        ] = []

        for url in urls:
            matched_target = (
                self._matched_target_term(
                    url,
                    target_terms,
                )
            )

            if matched_target:
                score = (
                    100
                    + len(
                        self._normalize_for_match(
                            matched_target
                        )
                    )
                )

                scored.append(
                    (
                        score,
                        url,
                        (
                            "target match: "
                            f"{matched_target}"
                        ),
                    )
                )

                continue

            matched_keyword = (
                self._matched_resource_keyword(
                    url,
                )
            )

            if matched_keyword:
                score = (
                    50
                    + len(matched_keyword)
                )

                scored.append(
                    (
                        score,
                        url,
                        (
                            "resource keyword: "
                            f"{matched_keyword}"
                        ),
                    )
                )

                continue

            parsed = urlparse(url)
            path = parsed.path.lower()

            specification_keywords = {
                "spec",
                "specs",
                "specification",
                "specifications",
                "technical",
                "features",
                "detail",
                "details",
                "overview",
                "product",
            }

            matched_spec_keyword = next(
                (
                    keyword
                    for keyword
                    in specification_keywords
                    if keyword in path
                ),
                None,
            )

            if matched_spec_keyword:
                scored.append(
                    (
                        20,
                        url,
                        (
                            "specification/product path: "
                            f"{matched_spec_keyword}"
                        ),
                    )
                )

                continue

            if self._looks_like_product_page(
                url
            ):
                scored.append(
                    (
                        5,
                        url,
                        "generic product page",
                    )
                )

                continue

            LOGGER.info(
                "[Resolver] Skipping low-value webpage: %s",
                url,
            )

        scored.sort(
            key=lambda item: (
                -item[0],
                item[1],
            ),
        )

        selected = scored[
            :self.max_webpages
        ]

        for score, url, reason in selected:
            LOGGER.info(
                "[Resolver] Candidate score=%d reason=%s url=%s",
                score,
                reason,
                url,
            )

        return [
            url
            for _, url, _
            in selected
        ]

    @staticmethod
    def _matched_target_term(
        url: str,
        target_terms: list[str] | None,
    ) -> str | None:
        if not target_terms:
            return None

        normalized_url = (
            ResourceResolver._normalize_for_match(
                url
            )
        )

        for term in target_terms:
            normalized_term = (
                ResourceResolver._normalize_for_match(
                    term
                )
            )

            if not normalized_term:
                continue

            if normalized_term in normalized_url:
                return term

        return None

    @staticmethod
    def _matched_resource_keyword(
        url: str,
    ) -> str | None:
        parsed = urlparse(url)

        haystack = (
            f"{parsed.netloc.lower()} "
            f"{parsed.path.lower()}"
        )

        resource_keywords = (
            "datasheet",
            "data-sheet",
            "manual",
            "manuals",
            "documentation",
            "document",
            "documents",
            "catalog",
            "catalogue",
            "brochure",
            "guide",
            "guides",
            "technical",
            "resource",
            "resources",
            "download",
            "downloads",
            "spec",
            "specs",
            "specification",
            "specifications",
            "installation",
            "operation",
            "service",
            "maintenance",
        )

        for keyword in resource_keywords:
            if keyword in haystack:
                return keyword

        return None

    @classmethod
    def _language_variant_key(
        cls,
        url: str,
    ) -> tuple[str, str | None]:
        """
        Return a conservative document identity and detected language.

        Only explicit two-letter language tokens in the filename are
        recognized. The rightmost recognized token is treated as the
        language code.
        """
        parsed = urlparse(url)
        filename = parsed.path.rsplit("/", 1)[-1]
        stem = re.sub(r"\.pdf$", "", filename, flags=re.IGNORECASE)
        pattern = re.compile(
            r"(?P<prefix>.*?)(?:[_\-.](?P<lang>[a-z]{2}))(?=[_\-.]|$)",
            re.IGNORECASE,
        )

        for match in reversed(list(pattern.finditer(stem))):
            language = match.group("lang").lower()
            if language not in cls.LANGUAGE_CODES:
                continue

            identity = f"{match.group('prefix')}{stem[match.end():]}"
            identity = re.sub(r"[_\-.]+", "_", identity).strip("_")
            if identity:
                return identity.lower(), language

        return stem.lower(), None

    @classmethod
    def _deduplicate_language_variants(
        cls,
        urls: list[str],
    ) -> list[str]:
        """
        Remove obvious language variants of the same document.

        English is preferred only when the normalized document identity is
        the same. Different document identities are always preserved.
        """
        groups: dict[str, list[tuple[str, str | None]]] = {}

        for url in urls:
            identity, language = cls._language_variant_key(url)
            groups.setdefault(identity, []).append((url, language))

        selected: list[str] = []

        for identity, candidates in groups.items():
            if len(candidates) == 1:
                selected.append(candidates[0][0])
                continue

            candidates.sort(
                key=lambda item: (
                    cls.LANGUAGE_PRIORITY.get(item[1], 998)
                    if item[1] is not None
                    else 999,
                    item[0],
                )
            )

            chosen_url, chosen_language = candidates[0]
            selected.append(chosen_url)

            for url, language in candidates[1:]:
                LOGGER.info(
                    "[Resolver] Language duplicate skipped: "
                    "%s (%s) -> keeping %s (%s)",
                    url,
                    language or "unknown",
                    chosen_url,
                    chosen_language or "unknown",
                )

        return selected

    @staticmethod
    def _looks_like_document_url(
        url: str,
    ) -> bool:
        """
        Cheap URL-only test.

        This must never perform network I/O.
        """

        parsed = urlparse(url)

        haystack = (
            f"{parsed.netloc.lower()} "
            f"{parsed.path.lower()}"
        )

        document_keywords = (
            "pdf",
            "datasheet",
            "data-sheet",
            "manual",
            "manuals",
            "documentation",
            "document",
            "documents",
            "catalog",
            "catalogue",
            "brochure",
            "guide",
            "guides",
            "technical",
            "resource",
            "resources",
            "download",
            "downloads",
            "spec",
            "specs",
            "specification",
            "specifications",
            "installation",
            "operation",
            "service",
            "maintenance",
        )

        return any(
            keyword in haystack
            for keyword in document_keywords
        )

    @staticmethod
    def _looks_like_product_page(
        url: str,
    ) -> bool:
        path = urlparse(url).path.lower()

        return (
            "/product/" in path
            or "/products/" in path
            or "/item/" in path
            or "/items/" in path
        )

    @staticmethod
    def _normalize_for_match(
        value: str,
    ) -> str:
        return re.sub(
            r"[^a-z0-9]+",
            "",
            value.lower(),
        )

    @staticmethod
    def _normalize_url(
        url: str,
    ) -> str:
        parsed = urlparse(url)

        parsed = parsed._replace(
            fragment="",
        )

        return urlunparse(parsed)

    @staticmethod
    def _is_supported_url(
        url: str,
    ) -> bool:
        return urlparse(
            url
        ).scheme.lower() in {
            "http",
            "https",
        }

    @staticmethod
    def _is_pdf_url(
        url: str,
    ) -> bool:
        return urlparse(
            url
        ).path.lower().endswith(
            ".pdf"
        )

    @staticmethod
    def _is_relevant_url(
        url: str,
    ) -> bool:
        parsed = urlparse(url)

        hostname = (
            parsed.hostname or ""
        ).lower()

        path = parsed.path.lower()

        blocked_hosts = {
            "facebook.com",
            "www.facebook.com",
            "twitter.com",
            "www.twitter.com",
            "x.com",
            "www.x.com",
            "linkedin.com",
            "www.linkedin.com",
            "instagram.com",
            "www.instagram.com",
            "pinterest.com",
            "www.pinterest.com",
        }

        if hostname in blocked_hosts:
            return False

        if hostname.endswith(
            "onelink.to"
        ):
            return False

        blocked_path_prefixes = {
            "/customer/account",
            "/login",
            "/register",
            "/account",
            "/checkout",
            "/cart",
        }

        if any(
            path.startswith(prefix)
            for prefix in blocked_path_prefixes
        ):
            return False

        path_segments = [
            segment
            for segment
            in path.split("/")
            if segment
        ]

        blocked_segments = {
            "wishlist",
            "myaccount",
            "login",
            "register",
            "cart",
            "checkout",
        }

        if any(
            segment in blocked_segments
            for segment in path_segments
        ):
            return False

        return True