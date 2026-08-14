from __future__ import annotations

import hashlib

from models.document_models import Document


class EvidenceBuilder:
    """
    Build a deterministic evidence package from research documents.

    Performs only safe evidence reduction:
    - removes empty documents
    - removes duplicate URLs
    - removes duplicate document content
    - preserves useful provenance
    - preserves complete content of retained documents
    """

    def build(
        self,
        documents: list[Document],
    ) -> str:
        sections: list[str] = []

        seen_urls: set[str] = set()
        seen_content: set[str] = set()

        output_index = 0

        for document in documents:
            content = (
                document.content
                or ""
            ).strip()

            # -------------------------------------------------
            # Ignore empty documents.
            # -------------------------------------------------
            if not content:
                continue

            metadata = document.metadata or {}

            url = (
                metadata.get("url")
                or metadata.get("source_url")
                or ""
            ).strip()

            # -------------------------------------------------
            # Deduplicate by URL.
            #
            # If the same document was discovered through
            # multiple research paths, keep the first copy.
            # -------------------------------------------------
            normalized_url = url.rstrip("/").lower()

            if normalized_url:
                if normalized_url in seen_urls:
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
                continue

            seen_content.add(
                content_hash
            )

            output_index += 1

            sections.append(
                self._format_document(
                    output_index,
                    document,
                    content=content,
                    url=url,
                )
            )

        if not sections:
            return (
                "NO EVIDENCE DOCUMENTS WERE PROVIDED."
            )

        return "\n\n".join(
            sections
        )

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