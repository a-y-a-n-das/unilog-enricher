from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from database import repositories
from database.models import Job, JobRow
from database.connection import SessionLocal
from sqlalchemy import select

from api.storage import get_output_file_path


def generate_output(job_id: str) -> Path | None:
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if job is None:
            return None

        rows = session.execute(
            select(JobRow)
            .where(JobRow.job_id == job.id)
            .order_by(JobRow.row_number)
        ).scalars().all()

        if not rows:
            return None

        output_path = get_output_file_path(job_id, job.input_filename, job.input_format)

        fieldnames = ["row_number", "status"]
        all_keys: set[str] = set()

        for row in rows:
            if row.result_data:
                for key in row.result_data.keys():
                    all_keys.add(f"result_{key}")
            if row.error_message:
                all_keys.add("error_message")

        sorted_keys = sorted(all_keys)
        fieldnames.extend(sorted_keys)

        if job.input_format == "xlsx":
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(fieldnames)
            for row in rows:
                row_data = {"row_number": row.row_number, "status": row.status}
                if row.result_data:
                    for key, value in row.result_data.items():
                        row_data[f"result_{key}"] = value
                if row.error_message:
                    row_data["error_message"] = row.error_message
                ws.append([row_data.get(key, "") for key in fieldnames])
            wb.save(output_path)
        else:
            with output_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    row_data = {"row_number": row.row_number, "status": row.status}
                    if row.result_data:
                        for key, value in row.result_data.items():
                            row_data[f"result_{key}"] = value
                    if row.error_message:
                        row_data["error_message"] = row.error_message
                    writer.writerow(row_data)

        job.output_file_path = str(output_path)
        session.add(job)
        session.commit()

        return output_path