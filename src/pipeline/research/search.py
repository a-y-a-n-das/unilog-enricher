import os
from dataclasses import dataclass
from dotenv import load_dotenv
from tavily import TavilyClient

from models.search_models import SearchResult

load_dotenv()


@dataclass
class SearchUsage:
    """Usage information from a single Tavily search request."""
    credits_used: int
    credits_remaining: int | None = None


class TavilySearch:
    def __init__(self) -> None:
        api_key = os.getenv("TAVILY_API_KEY")

        if not api_key:
            raise ValueError("TAVILY_API_KEY is not set")

        self.client = TavilyClient(api_key=api_key)

    def search(self, query: str) -> tuple[list[SearchResult], SearchUsage]:
        response = self.client.search(
            query=query,
            search_depth="advanced",
        )

        # Extract usage information from Tavily response
        usage_data = response.get("usage", {})
        credits_used = usage_data.get("credits_used", 2)  # Default to 2 for advanced search
        credits_remaining = usage_data.get("credits_remaining")

        usage = SearchUsage(
            credits_used=credits_used,
            credits_remaining=credits_remaining,
        )

        results = [
            SearchResult(
                title=result["title"],
                url=result["url"],
                content=result["content"],
                score=result.get("score"),
            )
            for result in response.get("results", [])
        ]

        return results, usage


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