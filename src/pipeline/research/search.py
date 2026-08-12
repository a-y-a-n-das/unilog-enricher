import os

from dotenv import load_dotenv
from tavily import TavilyClient

from models.search_models import SearchResult

load_dotenv()


class TavilySearch:
    def __init__(self) -> None:
        api_key = os.getenv("TAVILY_API_KEY")

        if not api_key:
            raise ValueError("TAVILY_API_KEY is not set")

        self.client = TavilyClient(api_key=api_key)

    def search(self, query: str) -> list[SearchResult]:
        response = self.client.search(
            query=query,
            search_depth="advanced",
        )

        return [
            SearchResult(
                title=result["title"],
                url=result["url"],
                content=result["content"],
                score=result.get("score"),
            )
            for result in response.get("results", [])
        ]


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