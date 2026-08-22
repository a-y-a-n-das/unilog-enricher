from __future__ import annotations

import hashlib
import logging
import re

from models.document_models import Document
from models.input_models import InputRecord


LOGGER = logging.getLogger(__name__)


class EvidenceBuilder:
    """
    Build a deterministic evidence package from research documents.

    Performs only safe evidence reduction:
    - removes empty documents
    - removes duplicate URLs
    - removes duplicate document content
    - filters irrelevant manufacturer PDFs (no target MPN/identifiers)
    - preserves useful provenance
    - preserves complete content of retained documents

    Diagnostic logging reports:
    - input document count
    - retained document count
    - empty documents
    - duplicate URLs
    - duplicate content
    - filtered irrelevant manufacturer PDFs
    - raw content size
    - final evidence size
    """

    def build(
        self,
        documents: list[Document],
        record: InputRecord | None = None,
    ) -> str:
        sections: list[str] = []

        seen_urls: set[str] = set()
        seen_content: set[str] = set()

        output_index = 0

        total_raw_chars = 0
        empty_count = 0
        duplicate_url_count = 0
        duplicate_content_count = 0
        filtered_irrelevant_count = 0

        LOGGER.info(
            "[Evidence] Input documents: %d",
            len(documents),
        )

        # Extract target identifiers for relevance filtering
        target_identifiers = self._extract_target_identifiers(record)

        for document_index, document in enumerate(
            documents,
            start=1,
        ):
            content = (
                document.content
                or ""
            ).strip()

            raw_chars = len(content)
            total_raw_chars += raw_chars

            metadata = document.metadata or {}

            url = (
                metadata.get("url")
                or metadata.get("source_url")
                or ""
            ).strip()

            document_type = metadata.get(
                "document_type",
                document.source,
            )

            # -------------------------------------------------
            # Skip excessively large documents (>100K chars).
            # -------------------------------------------------
            MAX_DOC_CHARS = 100_000
            if raw_chars > MAX_DOC_CHARS:
                LOGGER.info(
                    "[Evidence] #%d SKIPPED_LARGE | "
                    "type=%s | chars=%d | url=%s",
                    document_index,
                    document_type,
                    raw_chars,
                    url,
                )
                continue

            # -------------------------------------------------
            # Ignore empty documents.
            # -------------------------------------------------
            if not content:
                empty_count += 1

                LOGGER.info(
                    "[Evidence] #%d EMPTY | type=%s | chars=%d | url=%s",
                    document_index,
                    document_type,
                    raw_chars,
                    url,
                )

                continue

            # -------------------------------------------------
            # Filter irrelevant manufacturer PDFs.
            # -------------------------------------------------
            if self._is_irrelevant_manufacturer_pdf(
                document, content, url, document_type, target_identifiers
            ):
                filtered_irrelevant_count += 1

                LOGGER.info(
                    "[Evidence] #%d FILTERED_IRRELEVANT_MFR_PDF | "
                    "type=%s | chars=%d | url=%s",
                    document_index,
                    document_type,
                    raw_chars,
                    url,
                )

                continue

            # -------------------------------------------------
            # Deduplicate by URL.
            #
            # If the same document was discovered through
            # multiple research paths, keep the first copy.
            # -------------------------------------------------
            normalized_url = url.rstrip("/").lower()

            if normalized_url:
                if normalized_url in seen_urls:
                    duplicate_url_count += 1

                    LOGGER.info(
                        "[Evidence] #%d DUPLICATE_URL | "
                        "type=%s | chars=%d | url=%s",
                        document_index,
                        document_type,
                        raw_chars,
                        url,
                    )

                    continue

                seen_urls.add(
                    normalized_url
                )

            # -------------------------------------------------
            # Deduplicate identical content.
            #
            # Hashing avoids storing large content strings in
            # the seen set.
            # -------------------------------------------------
            content_hash = hashlib.sha256(
                content.encode("utf-8")
            ).hexdigest()

            if content_hash in seen_content:
                duplicate_content_count += 1

                LOGGER.info(
                    "[Evidence] #%d DUPLICATE_CONTENT | "
                    "type=%s | chars=%d | url=%s",
                    document_index,
                    document_type,
                    raw_chars,
                    url,
                )

                continue

            seen_content.add(
                content_hash
            )

            output_index += 1

            LOGGER.info(
                "[Evidence] #%d RETAINED | "
                "type=%s | chars=%d | url=%s",
                document_index,
                document_type,
                raw_chars,
                url,
            )

            sections.append(
                self._format_document(
                    output_index,
                    document,
                    content=content,
                    url=url,
                )
            )

        # -----------------------------------------------------
        # No evidence.
        # -----------------------------------------------------
        if not sections:
            evidence = (
                "NO EVIDENCE DOCUMENTS WERE PROVIDED."
            )

            LOGGER.info(
                "[Evidence] Summary: "
                "input=%d retained=%d empty=%d "
                "duplicate_url=%d duplicate_content=%d "
                "filtered_irrelevant=%d "
                "raw_chars=%d evidence_chars=%d",
                len(documents),
                output_index,
                empty_count,
                duplicate_url_count,
                duplicate_content_count,
                filtered_irrelevant_count,
                total_raw_chars,
                len(evidence),
            )

            return evidence

        evidence = "\n\n".join(
            sections
        )

        # -----------------------------------------------------
        # Final evidence diagnostics.
        # -----------------------------------------------------
        LOGGER.info(
            "[Evidence] Summary: "
            "input=%d retained=%d empty=%d "
            "duplicate_url=%d duplicate_content=%d "
            "filtered_irrelevant=%d "
            "raw_chars=%d evidence_chars=%d",
            len(documents),
            output_index,
            empty_count,
            duplicate_url_count,
            duplicate_content_count,
            filtered_irrelevant_count,
            total_raw_chars,
            len(evidence),
        )

        return evidence

    @staticmethod
    def _extract_target_identifiers(record: InputRecord | None) -> list[str]:
        """Extract product identifiers from the input record for relevance filtering."""
        if record is None:
            return []

        identifiers: set[str] = set()
        data = record.data or {}

        # Common identifier fields
        identifier_fields = [
            "ManufacturerPartNumber",
            "Mfg_Part_Num",
            "MPN",
            "Part_Desc",
            "Product",
            "SKU - MY_PART_NUMBER",
            "PART_NUMBER",
        ]

        for field in identifier_fields:
            value = str(data.get(field, "")).strip()
            if value and value not in ("-- Unbranded --", "-- No Unilog Brand --", "-- No DIB Brand --", "N/A"):
                identifiers.add(value.lower())

        # Also extract alphanumeric tokens from manufacturer field
        manufacturer = str(data.get("Manufacturer", "")).strip()
        if manufacturer:
            # Extract potential MPNs/part numbers from manufacturer string
            tokens = re.findall(r"[A-Z0-9][A-Z0-9\-]{3,}", manufacturer)
            identifiers.update(t.lower() for t in tokens)

        return list(identifiers)

    @staticmethod
    def _is_irrelevant_manufacturer_pdf(
        document: Document,
        content: str,
        url: str,
        document_type: str,
        target_identifiers: list[str],
    ) -> bool:
        """
        Filter out manufacturer PDFs that don't mention any target identifiers.

        Only applies to PDF documents from manufacturer/official sources.
        """
        # Only filter PDFs
        is_pdf = document_type == "pdf" or url.lower().endswith(".pdf")
        if not is_pdf:
            return False

        # Check if it's from a manufacturer/official source
        metadata = document.metadata or {}
        source_url = metadata.get("source_url", "") or ""
        combined_url = f"{source_url} {url}".lower()

        manufacturer_domains = [
            "mirka.com",
            "diablotools.com",
            "milwaukeetool.com",
        ]

        is_manufacturer_source = any(domain in combined_url for domain in manufacturer_domains)

        if not is_manufacturer_source:
            return False

        if not target_identifiers:
            # No identifiers to check against, don't filter
            return False

        # Check if any target identifier appears in the content
        content_lower = content.lower()
        for identifier in target_identifiers:
            if identifier in content_lower:
                return False  # Relevant - contains target identifier

        # No target identifier found - filter this manufacturer PDF
        return True

    @staticmethod
    def _format_document(
        index: int,
        document: Document,
        *,
        content: str,
        url: str,
    ) -> str:
        metadata = document.metadata or {}

        document_type = metadata.get(
            "document_type",
            document.source,
        )

        source_url = (
            metadata.get(
                "source_url",
                "",
            )
            or ""
        ).strip()

        lines = [
            f"===== SOURCE {index} =====",
            f"DOCUMENT TYPE: {document_type}",
        ]

        if url:
            lines.append(
                f"URL: {url}"
            )

        if (
            source_url
            and source_url.rstrip("/")
            != url.rstrip("/")
        ):
            lines.append(
                f"SOURCE URL: {source_url}"
            )

        lines.extend(
            [
                "",
                "CONTENT:",
                content,
                "",
                f"===== END SOURCE {index} =====",
            ]
        )

        return "\n".join(lines)

    @staticmethod
    def _format_document(
        index: int,
        document: Document,
        *,
        content: str,
        url: str,
    ) -> str:
        metadata = document.metadata or {}

        document_type = metadata.get(
            "document_type",
            document.source,
        )

        source_url = (
            metadata.get(
                "source_url",
                "",
            )
            or ""
        ).strip()

        lines = [
            f"===== SOURCE {index} =====",
            f"DOCUMENT TYPE: {document_type}",
        ]

        if url:
            lines.append(
                f"URL: {url}"
            )

        if (
            source_url
            and source_url.rstrip("/")
            != url.rstrip("/")
        ):
            lines.append(
                f"SOURCE URL: {source_url}"
            )

        lines.extend(
            [
                "",
                "CONTENT:",
                content,
                "",
                f"===== END SOURCE {index} =====",
            ]
        )

        return "\n".join(lines)