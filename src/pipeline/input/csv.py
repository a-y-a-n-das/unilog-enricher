import csv
from pathlib import Path
from typing import Any

from models.input_models import InputRecord


def load_input_csv(path: str | Path) -> list[InputRecord]:
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    with path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.reader(file)

        try:
            headers = next(reader)
        except StopIteration:
            raise ValueError("Input file is empty")

        headers = [
            str(header).strip() if header is not None else ""
            for header in headers
        ]

        if any(not header for header in headers):
            raise ValueError("Input file contains an empty column header")

        seen_headers: set[str] = set()
        for header in headers:
            if header in seen_headers:
                raise ValueError(f"Duplicate column header: {header}")
            seen_headers.add(header)

        records: list[InputRecord] = []

        for row_number, row in enumerate(reader, start=2):
            if not any(value.strip() for value in row):
                continue

            data: dict[str, Any] = dict(zip(headers, row))

            records.append(
                InputRecord(
                    row_number=row_number,
                    data=data,
                )
            )

    return records