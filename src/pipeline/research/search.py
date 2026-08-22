import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx
from dotenv import load_dotenv

from models.search_models import SearchResult

load_dotenv()

LOGGER = logging.getLogger(__name__)

DEFAULT_NUM_RESULTS = 10
DEFAULT_HIGHLIGHTS_MAX_CHARS = 1800


@dataclass
class SearchUsage:
    """Usage information from a single Exa search request."""

    credits_used: int
    cost_dollars: float | None = None
    credits_remaining: int | None = None


class ExaSearch:
    """Exa search provider compatible with the internal SearchResult contract."""

    def __init__(self) -> None:
        api_key = os.getenv("EXA_API_KEY")

        if not api_key:
            raise ValueError("EXA_API_KEY is not set")

        self.api_key = api_key
        self.base_url = "https://api.exa.ai"

    def search(self, query: str) -> tuple[list[SearchResult], SearchUsage]:
        """Execute a search query and return normalized results."""
        payload = {
            "query": query,
            "numResults": DEFAULT_NUM_RESULTS,
            "type": "auto",
            "contents": {
                "highlights": {
                    "maxCharacters": DEFAULT_HIGHLIGHTS_MAX_CHARS,
                }
            },
        }

        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.base_url}/search",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

        except httpx.HTTPStatusError as e:
            LOGGER.error("Exa search HTTP error: %s - %s", e.response.status_code, e.response.text)
            raise
        except httpx.RequestError as e:
            LOGGER.error("Exa search request error: %s", e)
            raise
        except Exception as e:
            LOGGER.error("Exa search unexpected error: %s", e)
            raise

        results = self._normalize_results(data.get("results", []))

        cost_dollars = None
        cost_data = data.get("costDollars", {})
        if isinstance(cost_data, dict):
            cost_dollars = cost_data.get("total")

        usage = SearchUsage(
            credits_used=1,
            cost_dollars=cost_dollars,
            credits_remaining=None,
        )

        return results, usage

    def _normalize_results(self, raw_results: list[dict[str, Any]]) -> list[SearchResult]:
        """Map Exa API response to internal SearchResult contract."""
        normalized: list[SearchResult] = []

        for result in raw_results:
            url = result.get("url")
            if not url:
                continue

            title = result.get("title", "")
            highlights = result.get("highlights", [])
            content = "\n".join(highlights) if highlights else ""
            score = result.get("score")

            normalized.append(
                SearchResult(
                    title=title,
                    url=url,
                    content=content,
                    score=score,
                )
            )

        return normalized


def deduplicate_results(
    results: list[SearchResult],
) -> list[SearchResult]:
    seen: set[str] = set()
    unique: list[SearchResult] = []

    for result in results:
        url = result.url.strip().lower().rstrip("/")

        if url in seen:
            continue

        seen.add(url)
        unique.append(result)

    return unique