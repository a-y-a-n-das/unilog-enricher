import logging
import os
from urllib.parse import urlparse

from dotenv import load_dotenv
from firecrawl import FirecrawlApp
import httpx

from models.document_models import Document
from pipeline.ingestion.firecrawl_limiter import (
    FirecrawlRateLimitError,
    get_firecrawl_limiter,
)

LOGGER = logging.getLogger(__name__)

load_dotenv()


class WebScraper:
    def __init__(self) -> None:
        api_key = os.getenv("FIRECRAWL_API_KEY")

        if not api_key:
            raise ValueError(
                "FIRECRAWL_API_KEY is not set"
            )

        self.client = FirecrawlApp(api_key=api_key)
        self._limiter = get_firecrawl_limiter()

    def scrape(self, url: str) -> Document:
        self._validate_url(url)

        def _do_scrape():
            return self.client.scrape_url(
                url=url,
                formats=["markdown", "links"],
            )

        try:
            response = self._limiter.execute_with_retry(_do_scrape, url)

        except FirecrawlRateLimitError as exc:
            LOGGER.error(
                "Firecrawl rate limit exhausted for %s after retries: %s",
                url,
                exc,
            )
            return Document(
                source="webpage",
                content="",
                metadata={
                    "url": url,
                    "error": f"rate_limit_exhausted: {exc}",
                    "scrape_status": "rate_limited",
                },
                images=[],
                links=[],
            )

        except Exception as exc:
            LOGGER.exception(
                "Failed to scrape webpage: %s",
                url,
            )

            return Document(
                source="webpage",
                content="",
                metadata={
                    "url": url,
                    "error": str(exc),
                    "scrape_status": "failed",
                },
                images=[],
                links=[],
            )

        metadata = {}

        response_metadata = getattr(
            response,
            "metadata",
            None,
        )

        if response_metadata is not None:
            if hasattr(response_metadata, "model_dump"):
                metadata = response_metadata.model_dump()
            elif isinstance(response_metadata, dict):
                metadata = response_metadata

        content = getattr(
            response,
            "markdown",
            "",
        ) or ""

        links = getattr(
            response,
            "links",
            None,
        ) or []

        images = getattr(
            response,
            "images",
            None,
        ) or []

        return Document(
            source="webpage",
            content=content,
            metadata={
                "url": url,
                **metadata,
                "scrape_status": "success",
            },
            images=images,
            links=links,
        )

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = urlparse(url)

        if parsed.scheme not in {"http", "https"}:
            raise ValueError(
                f"Invalid URL scheme: {parsed.scheme!r}"
            )

        if not parsed.netloc:
            raise ValueError(
                f"Invalid URL: {url}"
            )