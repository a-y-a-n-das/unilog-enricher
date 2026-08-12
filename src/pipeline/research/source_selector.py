import json
import logging
import re
from pathlib import Path

from models.input_models import InputRecord
from models.research_models import SourceAnalysis, SourceVerificationResult
from pipeline.llm.client import LLMClient
from models.search_models import SearchResult

LOGGER = logging.getLogger(__name__)


PROMPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "prompts"
    / "research"
    / "select_sources.md"
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

    # Direct JSON
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # JSON inside a Markdown code fence
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

    # Find the first JSON object or array
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


def _format_results(
    results: list[SearchResult],
) -> str:
    return json.dumps(
        [
            {
                "title": result.title,
                "url": result.url,
                "content": result.content,
                "score": result.score,
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
        # Allow a bare list as a defensive fallback.
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

    prompt = load_prompt()

    prompt = prompt.replace(
        "{{product}}",
        _format_product(record),
    )

    prompt = prompt.replace(
        "{{results}}",
        _format_results(results),
    )
###
    print("SOURCE SELECTOR PROMPT LENGTH:", len(prompt))

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