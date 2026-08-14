import hashlib
from pathlib import Path
from urllib.parse import urlparse

import requests


class Downloader:
    def __init__(
        self,
        download_dir: str | Path = "data/downloads",
    ) -> None:
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def download(
        self,
        url: str,
        workspace: str | Path | None = None,
    ) -> Path:
        response = requests.get(
            url,
            timeout=30,
            headers={
                "User-Agent": "UniLog/1.0",
            },
        )
        response.raise_for_status()

        content_type = (
            response.headers
            .get("Content-Type", "")
            .lower()
        )

        if "application/pdf" not in content_type:
            raise ValueError(
                "Expected PDF but received "
                f"Content-Type: {content_type}"
            )

        parsed = urlparse(url)
        filename = Path(parsed.path).name

        if not filename.lower().endswith(".pdf"):
            filename = (
                f"{hashlib.sha256(url.encode()).hexdigest()[:16]}"
                ".pdf"
            )

        output_dir = workspace if workspace is not None else self.download_dir
        output_path = output_dir / filename
        output_path.write_bytes(response.content)

        return output_path

    def is_pdf(self, url: str) -> bool:
        try:
            response = requests.head(
                url,
                timeout=15,
                allow_redirects=True,
                headers={
                    "User-Agent": "UniLog/1.0",
                },
            )

            content_type = (
                response.headers
                .get("Content-Type", "")
                .lower()
            )

            if (
                response.ok
                and "application/pdf" in content_type
            ):
                return True

        except requests.RequestException:
            pass

        try:
            response = requests.get(
                url,
                timeout=15,
                stream=True,
                allow_redirects=True,
                headers={
                    "User-Agent": "UniLog/1.0",
                },
            )

            try:
                content_type = (
                    response.headers
                    .get("Content-Type", "")
                    .lower()
                )

                return (
                    response.ok
                    and "application/pdf" in content_type
                )

            finally:
                response.close()

        except requests.RequestException:
            pass

        return False