import json
import logging
import re
from pathlib import Path

from models.document_models import Document
from models.extraction_models import ExtractedProduct
from models.input_models import InputRecord
from pipeline.extraction.evidence import EvidenceBuilder
from pipeline.llm.client import LLMClient

LOGGER = logging.getLogger(__name__)

PROMPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "prompts"
    / "extraction"
    / "extract_product.md"
)


class ProductExtractor:
    """
    Extract one complete product record from an input row and
    its supplied research evidence.

    The LLM is responsible only for producing an ExtractedProduct.
    """

    def __init__(
        self,
        llm: LLMClient,
        evidence_builder: EvidenceBuilder | None = None,
    ) -> None:
        self.llm = llm
        self.evidence_builder = (
            evidence_builder or EvidenceBuilder()
        )

    @staticmethod
    def _load_prompt() -> str:
        if not PROMPT_PATH.exists():
            raise FileNotFoundError(
                f"Extraction prompt not found: {PROMPT_PATH}"
            )

        return PROMPT_PATH.read_text(
            encoding="utf-8"
        ).strip()

    @staticmethod
    def _parse_json_response(
        content: str,
    ) -> dict | None:
        """
        Extract a JSON object from an LLM response.

        Supports:
        - plain JSON
        - JSON inside a markdown code fence
        - JSON embedded in surrounding text
        """

        if not content or not content.strip():
            return None

        content = content.strip()

        # -----------------------------------------------------
        # Direct JSON.
        # -----------------------------------------------------
        try:
            parsed = json.loads(content)

            if isinstance(parsed, dict):
                return parsed

        except json.JSONDecodeError:
            pass

        # -----------------------------------------------------
        # JSON inside markdown code fence.
        # -----------------------------------------------------
        fence_match = re.search(
            r"```(?:json)?\s*(\{.*\})\s*```",
            content,
            re.DOTALL,
        )

        if fence_match:
            try:
                parsed = json.loads(
                    fence_match.group(1)
                )

                if isinstance(parsed, dict):
                    return parsed

            except json.JSONDecodeError:
                pass

        # -----------------------------------------------------
        # Find the first JSON object in surrounding text.
        # -----------------------------------------------------
        start = content.find("{")

        if start < 0:
            return None

        depth = 0
        in_string = False
        escaped = False

        for index in range(
            start,
            len(content),
        ):
            char = content[index]

            if escaped:
                escaped = False
                continue

            if char == "\\" and in_string:
                escaped = True
                continue

            if char == '"':
                in_string = not in_string
                continue

            if in_string:
                continue

            if char == "{":
                depth += 1

            elif char == "}":
                depth -= 1

                if depth == 0:
                    candidate = content[
                        start : index + 1
                    ]

                    try:
                        parsed = json.loads(
                            candidate
                        )

                        if isinstance(parsed, dict):
                            return parsed

                    except json.JSONDecodeError:
                        return None

        return None

    @staticmethod
    def _format_input_record(
        record: InputRecord,
    ) -> str:
        """
        Serialize the target input row for the extraction prompt.
        """

        return json.dumps(
            {
                "row_number": record.row_number,
                "data": record.data,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    @staticmethod
    def _build_schema() -> str:
        """
        Generate the authoritative JSON schema directly from
        the Pydantic extraction model.
        """

        return json.dumps(
            ExtractedProduct.model_json_schema(),
            ensure_ascii=False,
            indent=2,
        )

    def _build_prompt(
        self,
        record: InputRecord,
        documents: list[Document],
    ) -> str:
        """
        Construct the complete extraction prompt.

        The prompt contains:
        1. master extraction rules
        2. target input row
        3. complete evidence package
        4. authoritative output schema
        """

        prompt = self._load_prompt()

        evidence = self.evidence_builder.build(
            documents
        )

        prompt = prompt.replace(
            "{{input_record}}",
            self._format_input_record(record),
        )

        prompt = prompt.replace(
            "{{evidence}}",
            evidence,
        )

        prompt = prompt.replace(
            "{{output_schema}}",
            self._build_schema(),
        )

        return prompt

    def extract(
        self,
        record: InputRecord,
        documents: list[Document],
    ) -> ExtractedProduct:
        """
        Extract one complete product record.

        Exactly one LLM generation call is made.
        """

        prompt = self._build_prompt(
            record,
            documents,
        )

        LOGGER.info(
            "Starting product extraction for row %d",
            record.row_number,
        )

        LOGGER.info(
            "Extraction prompt length: %d characters",
            len(prompt),
        )

        content = self.llm.generate(
            prompt
        )

        LOGGER.info(
            "Received extraction response: %d characters",
            len(content),
        )

        LOGGER.info(
            "Received extraction response: %d characters",
            len(content),
        )



        parsed = self._parse_json_response(
            content
        )

        if parsed is None:
            LOGGER.error(
                "Failed to parse extraction response as JSON"
            )

            LOGGER.debug(
                "Raw extraction response: %s",
                content[:5000],
            )

            raise ValueError(
                "Failed to parse extraction response as JSON"
            )

        # ---------------------------------------------------------
        # Enforce maximum collection sizes.
        #
        # These limits are defined by ExtractedProduct:
        # - item_features: max 20
        # - attributes: max 50
        #
        # Keep the first N items and discard anything beyond
        # the schema-defined maximum.
        # ---------------------------------------------------------

        MAX_ITEM_FEATURES = 20
        MAX_ATTRIBUTES = 50

        item_features = parsed.get("item_features")

        if isinstance(item_features, list):
            if len(item_features) > MAX_ITEM_FEATURES:
                LOGGER.warning(
                    "Extraction returned %d item features; "
                    "keeping first %d and discarding %d",
                    len(item_features),
                    MAX_ITEM_FEATURES,
                    len(item_features) - MAX_ITEM_FEATURES,
                )

            parsed["item_features"] = item_features[:MAX_ITEM_FEATURES]

        attributes = parsed.get("attributes")

        if isinstance(attributes, list):
            if len(attributes) > MAX_ATTRIBUTES:
                LOGGER.warning(
                    "Extraction returned %d attributes; "
                    "keeping first %d and discarding %d",
                    len(attributes),
                    MAX_ATTRIBUTES,
                    len(attributes) - MAX_ATTRIBUTES,
                )

            parsed["attributes"] = attributes[:MAX_ATTRIBUTES]

        try:
            result = ExtractedProduct.model_validate(
                parsed
            )

        except Exception as exc:
            LOGGER.error(
                "Extraction response failed schema validation: %s",
                exc,
            )

            raise ValueError(
                "Invalid ExtractedProduct response"
            ) from exc

        if result.row_number != record.row_number:
            raise ValueError(
                "Extracted row_number does not match "
                f"input row_number: "
                f"{result.row_number} != "
                f"{record.row_number}"
            )

        LOGGER.info(
            "Product extraction completed for row %d",
            record.row_number,
        )

        return result