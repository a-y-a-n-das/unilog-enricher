import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import pymupdf
import pymupdf4llm

from models.document_models import Document

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class OCRFastPathConfig:
    min_avg_chars_per_page: int = 200
    min_avg_words_per_page: int = 30
    min_alpha_ratio: float = 0.4
    max_repeated_char_ratio: float = 0.3
    min_pages_with_text_fraction: float = 0.5


DEFAULT_FAST_PATH_CONFIG = OCRFastPathConfig()


def assess_pdf_text_quality(
    pdf_path: Path,
    config: OCRFastPathConfig = DEFAULT_FAST_PATH_CONFIG,
) -> tuple[bool, dict]:
    """
    Assess whether a PDF contains sufficiently good native text
    to safely avoid OCR.

    Returns:
        (use_fast_path, metrics)
    """

    doc = None
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as exc:
        return False, {
            "reason": f"failed_to_open: {exc}",
            "page_count": 0,
        }

    try:
        page_count = len(doc)

        if page_count == 0:
            return False, {
                "reason": "empty_pdf",
                "page_count": 0,
            }

        total_chars = 0
        total_words = 0
        total_alpha_chars = 0
        total_chars_for_repeat = 0
        total_repeated_chars = 0
        pages_with_text = 0

        for page in doc:
            text = page.get_text()

            chars = len(text)
            words = len(text.split())

            total_chars += chars
            total_words += words

            if chars > 0:
                alpha_chars = sum(
                    1
                    for char in text
                    if char.isalnum()
                )
                total_alpha_chars += alpha_chars

                if chars > 1:
                    repeated = sum(
                        1
                        for i in range(1, chars)
                        if text[i] == text[i - 1]
                    )

                    total_repeated_chars += repeated
                    total_chars_for_repeat += chars - 1

            if chars >= 50:
                pages_with_text += 1

        avg_chars_per_page = total_chars / page_count
        avg_words_per_page = total_words / page_count

        alpha_ratio = (
            total_alpha_chars / total_chars
            if total_chars
            else 0.0
        )

        repeated_ratio = (
            total_repeated_chars / total_chars_for_repeat
            if total_chars_for_repeat
            else 0.0
        )

        pages_with_text_fraction = (
            pages_with_text / page_count
        )

        metrics = {
            "page_count": page_count,
            "total_chars": total_chars,
            "total_words": total_words,
            "avg_chars_per_page": round(
                avg_chars_per_page,
                1,
            ),
            "avg_words_per_page": round(
                avg_words_per_page,
                1,
            ),
            "alpha_ratio": round(
                alpha_ratio,
                3,
            ),
            "repeated_ratio": round(
                repeated_ratio,
                3,
            ),
            "pages_with_text": pages_with_text,
            "pages_with_text_fraction": round(
                pages_with_text_fraction,
                3,
            ),
        }

        criteria = {
            "avg_chars_per_page": (
                avg_chars_per_page
                >= config.min_avg_chars_per_page
            ),
            "avg_words_per_page": (
                avg_words_per_page
                >= config.min_avg_words_per_page
            ),
            "alpha_ratio": (
                alpha_ratio
                >= config.min_alpha_ratio
            ),
            "repeated_ratio": (
                repeated_ratio
                <= config.max_repeated_char_ratio
            ),
            "pages_with_text_fraction": (
                pages_with_text_fraction
                >= config.min_pages_with_text_fraction
            ),
        }

        metrics["criteria"] = criteria

        use_fast_path = all(criteria.values())

        if use_fast_path:
            metrics["reason"] = "all criteria passed"
        else:
            failed = [
                name
                for name, passed in criteria.items()
                if not passed
            ]

            metrics["reason"] = (
                f"failed criteria: {', '.join(failed)}"
            )

        return use_fast_path, metrics

    finally:
        if doc is not None:
            doc.close()


class PDFParser:
    def __init__(
        self,
        fast_path_config: OCRFastPathConfig | None = None,
    ) -> None:
        self.fast_path_config = (
            fast_path_config
            or DEFAULT_FAST_PATH_CONFIG
        )

    def parse(
        self,
        pdf_path: str | Path,
    ) -> Document:
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(
                f"PDF not found: {pdf_path}"
            )

        if not pdf_path.is_file():
            raise ValueError(
                f"PDF path is not a file: {pdf_path}"
            )

        start = perf_counter()

        use_fast_path, fast_path_metrics = (
            assess_pdf_text_quality(
                pdf_path,
                self.fast_path_config,
            )
        )

        if use_fast_path:
            LOGGER.info(
                "PDF fast path: %s "
                "(pages=%d, avg_chars=%.0f, alpha=%.2f)",
                pdf_path.name,
                fast_path_metrics["page_count"],
                fast_path_metrics["avg_chars_per_page"],
                fast_path_metrics["alpha_ratio"],
            )

            content, page_sources = (
                self._parse_without_ocr(
                    pdf_path,
                )
            )

            parser_mode = "fast_path_no_ocr"

        else:
            LOGGER.info(
                "PDF OCR path: %s (reason: %s)",
                pdf_path.name,
                fast_path_metrics.get(
                    "reason",
                    "unknown",
                ),
            )

            content, page_sources = (
                self._parse_with_ocr(
                    pdf_path,
                )
            )

            parser_mode = "ocr_enabled"

        elapsed = perf_counter() - start

        sha256 = hashlib.sha256(
            pdf_path.read_bytes()
        ).hexdigest()

        with pymupdf.open(pdf_path) as doc:
            page_count = len(doc)

        native_pages = sum(
            source == "native"
            for source in page_sources
        )

        ocr_pages = sum(
            source == "ocr"
            for source in page_sources
        )

        metadata = {
            "filename": pdf_path.name,
            "path": str(pdf_path.resolve()),
            "extension": pdf_path.suffix.lower(),
            "size_bytes": pdf_path.stat().st_size,
            "page_count": page_count,
            "image_count": 0,
            "sha256": sha256,
            "parser": f"pymupdf4llm_{parser_mode}",
            "parse_time_seconds": round(
                elapsed,
                2,
            ),
            "native_pages": native_pages,
            "ocr_pages": ocr_pages,
            "page_sources": page_sources,
            "fast_path_metrics": fast_path_metrics,
        }

        LOGGER.info(
            "PDF parsed: %s pages "
            "(%d native, %d ocr) mode=%s time=%.2fs",
            page_count,
            native_pages,
            ocr_pages,
            parser_mode,
            elapsed,
        )

        return Document(
            source="pdf",
            content=content,
            metadata=metadata,
            images=[],
            links=[],
        )

    def _parse_without_ocr(
        self,
        pdf_path: Path,
    ) -> tuple[str, list[str]]:
        """Parse a clearly text-based PDF without OCR."""

        content = pymupdf4llm.to_markdown(
            pdf_path,
            write_images=False,
            use_ocr=False,
        )

        with pymupdf.open(pdf_path) as doc:
            page_count = len(doc)

        return content, ["native"] * page_count

    def _parse_with_ocr(
        self,
        pdf_path: Path,
    ) -> tuple[str, list[str]]:
        """Parse a PDF with OCR enabled."""

        content = pymupdf4llm.to_markdown(
            pdf_path,
            write_images=False,
            use_ocr=True,
        )

        with pymupdf.open(pdf_path) as doc:
            page_count = len(doc)

        return content, ["ocr"] * page_count