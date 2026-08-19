from __future__ import annotations

import hashlib
import logging

from models.document_models import Document


LOGGER = logging.getLogger(__name__)


class EvidenceBuilder:
    """
    Build a deterministic evidence package from research documents.

    Performs only safe evidence reduction:
    - removes empty documents
    - removes duplicate URLs
    - removes duplicate document content
    - preserves useful provenance
    - preserves complete content of retained documents

    Diagnostic logging reports:
    - input document count
    - retained document count
    - empty documents
    - duplicate URLs
    - duplicate content
    - raw content size
    - final evidence size
    """

    def build(
        self,
        documents: list[Document],
    ) -> str:
        sections: list[str] = []

        seen_urls: set[str] = set()
        seen_content: set[str] = set()

        output_index = 0

        total_raw_chars = 0
        empty_count = 0
        duplicate_url_count = 0
        duplicate_content_count = 0

        LOGGER.info(
            "[Evidence] Input documents: %d",
            len(documents),
        )

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
                "raw_chars=%d evidence_chars=%d",
                len(documents),
                output_index,
                empty_count,
                duplicate_url_count,
                duplicate_content_count,
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
            "raw_chars=%d evidence_chars=%d",
            len(documents),
            output_index,
            empty_count,
            duplicate_url_count,
            duplicate_content_count,
            total_raw_chars,
            len(evidence),
        )

        return evidence

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