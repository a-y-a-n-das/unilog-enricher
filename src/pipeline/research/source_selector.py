import json
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

from models.input_models import InputRecord
from models.research_models import SourceVerificationResult
from models.search_models import SearchResult
from pipeline.llm.client import LLMClient


LOGGER = logging.getLogger(__name__)

PROMPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "prompts"
    / "research"
    / "select_sources.md"
)


# Conservative limits.
# These are deliberately easy to tune after measuring real runs.
MAX_SELECTOR_CANDIDATES = 30
CONTENT_PREVIEW_CHARS = 1800


# Obvious search/noise pages that are rarely useful as first-class research.
JUNK_PATH_TERMS = (
    "/login",
    "/signin",
    "/signup",
    "/register",
    "/cart",
    "/checkout",
    "/account",
    "/privacy",
    "/terms",
    "/cookie",
)

JUNK_TITLE_TERMS = (
    "login",
    "sign in",
    "register",
    "shopping cart",
    "checkout",
    "privacy policy",
    "terms of service",
)


def load_prompt() -> str:
    if not PROMPT_PATH.exists():
        raise FileNotFoundError(
            f"Prompt not found: {PROMPT_PATH}"
        )

    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def _parse_json_response(content: str) -> dict | list | None:
    """Safely parse JSON from an LLM response."""

    if not content or not content.strip():
        return None

    content = content.strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    fence_match = re.search(
        r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```",
        content,
        re.DOTALL,
    )

    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    starts = [
        (content.find("{"), "}"),
        (content.find("["), "]"),
    ]

    starts = [
        (position, closing)
        for position, closing in starts
        if position >= 0
    ]

    if not starts:
        return None

    start, closing_char = min(
        starts,
        key=lambda item: item[0],
    )

    opening_char = content[start]
    depth = 0

    for index in range(start, len(content)):
        char = content[index]

        if char == opening_char:
            depth += 1

        elif char == closing_char:
            depth -= 1

            if depth == 0:
                candidate = content[start:index + 1]

                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    return None

    return None


def _format_product(record: InputRecord) -> str:
    return json.dumps(
        {
            "row_number": record.row_number,
            "data": record.data,
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )


def _is_obvious_junk(result: SearchResult) -> bool:
    """Remove sources that are clearly not useful research candidates."""

    title = (result.title or "").strip().lower()
    url = (result.url or "").strip().lower()

    if any(term in title for term in JUNK_TITLE_TERMS):
        return True

    try:
        path = urlparse(url).path
    except ValueError:
        path = url

    if any(term in path for term in JUNK_PATH_TERMS):
        return True

    return False


def _normalize_url(url: str) -> str:
    """Normalize URLs enough to catch obvious duplicate search results."""

    url = url.strip().lower()

    # Remove fragments.
    url = url.split("#", 1)[0]

    # Remove a trailing slash except for the root.
    if url.endswith("/") and len(url) > len("https://x/"):
        url = url[:-1]

    return url


def _deduplicate_results(
    results: list[SearchResult],
) -> list[SearchResult]:
    """Keep the highest-scoring result for each normalized URL."""

    best_by_url: dict[str, SearchResult] = {}

    for result in results:
        normalized_url = _normalize_url(result.url)

        if not normalized_url:
            continue

        existing = best_by_url.get(normalized_url)

        if existing is None:
            best_by_url[normalized_url] = result
            continue

        existing_score = existing.score or 0
        current_score = result.score or 0

        if current_score > existing_score:
            best_by_url[normalized_url] = result

    return list(best_by_url.values())


def _prepare_selector_candidates(
    results: list[SearchResult],
) -> list[SearchResult]:


    original_count = len(results)

    # 1. Remove obvious junk.
    candidates = [
        result
        for result in results
        if not _is_obvious_junk(result)
    ]

    after_junk_filter = len(candidates)

    # 2. Remove duplicate URLs while preserving the best-scoring result.
    candidates = _deduplicate_results(candidates)

    after_deduplication = len(candidates)

    # 3. Preserve the existing discovery/search score.
    # Higher-scoring candidates get priority, while stable ordering is
    # retained for ties.
    candidates.sort(
        key=lambda result: result.score or 0,
        reverse=True,
    )

    # 4. Bound the number of candidates entering the LLM.
    candidates = candidates[:MAX_SELECTOR_CANDIDATES]

    LOGGER.info(
        "Source selector candidates: %d -> %d after junk filtering -> "
        "%d after deduplication -> %d sent to LLM",
        original_count,
        after_junk_filter,
        after_deduplication,
        len(candidates),
    )

    return candidates


def _truncate_content(content: str) -> str:
    """Keep source selection context bounded."""

    if not content:
        return ""

    content = content.strip()

    if len(content) <= CONTENT_PREVIEW_CHARS:
        return content

    return (
        content[:CONTENT_PREVIEW_CHARS].rstrip()
        + "\n...[content truncated for source selection]..."
    )


def _format_results(
    results: list[SearchResult],
) -> str:
    """
    Format lightweight source metadata for the selector.

    The selector does not need the complete scraped document.
    Full source content remains available to the downstream research stage.
    """

    return json.dumps(
        [
            {
                "title": result.title,
                "url": result.url,
                "score": result.score,
                "content_preview": _truncate_content(result.content),
            }
            for result in results
        ],
        ensure_ascii=False,
        indent=2,
    )


def _normalize_response(
    parsed: dict | list,
) -> SourceVerificationResult:
    """Normalize the expected source-selection response."""

    if isinstance(parsed, dict):
        sources = parsed.get("sources")

        if not isinstance(sources, list):
            raise ValueError(
                "Source selection response must contain a 'sources' list"
            )

    elif isinstance(parsed, list):
        sources = parsed

    else:
        raise ValueError(
            f"Unexpected response type: {type(parsed).__name__}"
        )

    return SourceVerificationResult.model_validate(
        {
            "sources": sources,
        }
    )


def select_sources(
    record: InputRecord,
    results: list[SearchResult],
    llm: LLMClient,
) -> SourceVerificationResult:
    """Evaluate search results and select useful research sources."""

    if not results:
        return SourceVerificationResult(sources=[])

    candidates = _prepare_selector_candidates(results)

    if not candidates:
        return SourceVerificationResult(sources=[])

    prompt = load_prompt()

    prompt = prompt.replace(
        "{{product}}",
        _format_product(record),
    )

    prompt = prompt.replace(
        "{{results}}",
        _format_results(candidates),
    )

    LOGGER.info(
        "Source selector prompt length: %d characters",
        len(prompt),
    )

    content = llm.generate(prompt)

    parsed = _parse_json_response(content)

    if parsed is None:
        LOGGER.warning(
            "Failed to parse source selection response as JSON: %s",
            content[:500],
        )
        raise ValueError(
            "Failed to parse source selection response as JSON"
        )

    try:
        return _normalize_response(parsed)

    except Exception as exc:
        LOGGER.warning(
            "Failed to validate source selection response: %s",
            exc,
        )
        raise ValueError(
            "Invalid source selection response"
        ) from exc