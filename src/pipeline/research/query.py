import json
import logging
import re
from pathlib import Path

from models.input_models import InputRecord
from pipeline.llm.client import LLMClient
from pydantic import BaseModel, Field

LOGGER = logging.getLogger(__name__)


PROMPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "prompts"
    / "research"
    / "generate_queries.md"
)

class QueryGenerationResult(BaseModel):
    queries: list[str] = Field(default_factory=list)

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

    # JSON inside a markdown code fence
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

    # Try to find the first JSON object or array
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

    start, closing_char = min(starts, key=lambda item: item[0])
    opening_char = content[start]

    depth = 0

    for index in range(start, len(content)):
        char = content[index]

        if char == opening_char:
            depth += 1
        elif char == closing_char:
            depth -= 1

            if depth == 0:
                candidate = content[start : index + 1]

                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    return None

    return None


def clean_queries(
    queries: list[str],
    max_queries: int | None = None,
) -> list[str]:
    """Normalize and deduplicate generated search queries."""

    cleaned: list[str] = []
    seen: set[str] = set()

    for query in queries:
        query = " ".join(query.split()).strip()

        if not query:
            continue

        normalized = query.lower()

        if normalized in seen:
            continue

        seen.add(normalized)
        cleaned.append(query)

        if max_queries is not None and len(cleaned) >= max_queries:
            break

    return cleaned


def _format_input_record(record: InputRecord) -> str:
    """Convert an InputRecord into JSON for the research prompt."""

    return json.dumps(
        {
            "row_number": record.row_number,
            "data": record.data,
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )


def generate_queries(
    record: InputRecord,
    llm: LLMClient,
    *,
    max_queries: int | None = None,
) -> list[str]:
    """Generate initial research queries for an input product."""

    prompt_template = load_prompt()

    prompt = prompt_template.replace(
        "{{input_record}}",
        _format_input_record(record),
    )

    content = llm.generate(prompt)

    parsed = _parse_json_response(content)

    if parsed is None:
        raise ValueError(
            "Failed to parse query generation response as JSON"
        )

    try:
        result = QueryGenerationResult.model_validate(parsed)
    except Exception as exc:
        LOGGER.warning(
            "Failed to validate query generation response: %s",
            exc,
        )
        raise ValueError(
            "Invalid query generation response"
        ) from exc

    return clean_queries(
        result.queries,
        max_queries=max_queries,
    )


