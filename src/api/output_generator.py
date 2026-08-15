from __future__ import annotations

import csv
import tempfile
from pathlib import Path
from typing import Any, Optional

from database import repositories
from database.models import Job, JobRow
from database.connection import SessionLocal
from sqlalchemy import select

from api.storage import get_output_file_path


def _get_input_headers(rows: list[JobRow]) -> list[str]:
    """Extract all unique input column headers from JobRow.input_data, preserving order of first appearance."""
    headers: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if row.input_data:
            for key in row.input_data.keys():
                if key not in seen:
                    seen.add(key)
                    headers.append(key)
    return headers


def _flatten_result_data(result_data: dict) -> dict:
    """Flatten ExtractedProduct result_data by extracting .value from ExtractedField/ExtractedAttribute objects."""
    flattened = {}
    for key, value in result_data.items():
        if key == "attributes" and isinstance(value, list):
            # Handle list of ExtractedAttribute objects
            for attr in value:
                if isinstance(attr, dict):
                    label = attr.get("label", "")
                    attr_value = attr.get("value")
                    uom = attr.get("uom")
                    if label:
                        # Extract the actual value from ExtractedField
                        if isinstance(attr_value, dict) and "value" in attr_value:
                            flat_value = attr_value["value"]
                        else:
                            flat_value = attr_value
                        if uom:
                            flattened[f"{key}_{label}"] = f"{flat_value} {uom}" if flat_value else ""
                        else:
                            flattened[f"{key}_{label}"] = flat_value
        elif key == "item_features" and isinstance(value, list):
            # Handle list of ExtractedField
            for i, feature in enumerate(value):
                if isinstance(feature, dict) and "value" in feature:
                    flattened[f"{key}_{i+1}"] = feature["value"]
                else:
                    flattened[f"{key}_{i+1}"] = str(feature)
        elif isinstance(value, dict):
            # ExtractedField or ExtractedAttribute structure
            if "value" in value:
                flattened[key] = value["value"]
            elif "label" in value and "value" in value:
                # ExtractedAttribute
                if isinstance(value["value"], dict) and "value" in value["value"]:
                    flattened[key] = value["value"]["value"]
                else:
                    flattened[key] = str(value)
            else:
                flattened[key] = str(value)
        else:
            flattened[key] = value
    return flattened


def _get_all_result_keys(rows: list[JobRow]) -> list[str]:
    """Extract all unique result_data keys from completed rows, sorted."""
    all_keys: set[str] = set()
    for row in rows:
        if row.result_data:
            # Use flattened keys
            flattened = _flatten_result_data(row.result_data)
            for key in flattened.keys():
                all_keys.add(f"result_{key}")
    return sorted(all_keys)


def _build_output_rows(rows: list[JobRow], input_headers: list[str], result_keys: list[str]) -> list[dict]:
    """Build output row data combining input_data, result_data, status, and error_message."""
    output_rows = []
    for row in rows:
        row_data: dict[str, Any] = {
            "row_number": row.row_number,
            "status": row.status,
        }
        # Original input columns
        if row.input_data:
            for key in input_headers:
                row_data[key] = row.input_data.get(key, "")
        # Enrichment/result columns
        if row.result_data:
            flattened = _flatten_result_data(row.result_data)
            for key, value in flattened.items():
                row_data[f"result_{key}"] = value
        # Error message for failed rows
        if row.error_message:
            row_data["error_message"] = row.error_message
        output_rows.append(row_data)
    return output_rows


def generate_output(job_id: str) -> Path | None:
    """Generate final persistent output for completed jobs. Sets job.output_file_path."""
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

        input_headers = _get_input_headers(rows)
        result_keys = _get_all_result_keys(rows)

        fieldnames = ["row_number", "status"]
        fieldnames.extend(input_headers)
        fieldnames.extend(result_keys)
        fieldnames.append("error_message")

        if job.input_format == "xlsx":
            import openpyxl
            wb = openpyxl.Workbook()

            # Sheet 1: Input - original input data only
            ws_input = wb.active
            ws_input.title = "Input"
            input_fieldnames = ["row_number"] + input_headers
            ws_input.append(input_fieldnames)
            for row in rows:
                row_data = {"row_number": row.row_number}
                if row.input_data:
                    for key in input_headers:
                        row_data[key] = row.input_data.get(key, "")
                ws_input.append([row_data.get(key, "") for key in input_fieldnames])

            # Sheet 2: Output - input + enrichment + status + error
            ws_output = wb.create_sheet("Output")
            output_fieldnames = ["row_number", "status"] + input_headers + _get_all_result_keys(rows) + ["error_message"]
            ws_output.append(output_fieldnames)
            for row in rows:
                row_data = {"row_number": row.row_number, "status": row.status}
                if row.input_data:
                    for key in input_headers:
                        row_data[key] = row.input_data.get(key, "")
                if row.result_data:
                    flattened = _flatten_result_data(row.result_data)
                    for key, value in flattened.items():
                        row_data[f"result_{key}"] = value
                if row.error_message:
                    row_data["error_message"] = row.error_message
                ws_output.append([row_data.get(key, "") for key in output_fieldnames])

            wb.save(output_path)
        else:
            with output_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    row_data = {"row_number": row.row_number, "status": row.status}
                    if row.input_data:
                        for key in input_headers:
                            row_data[key] = row.input_data.get(key, "")
                    if row.result_data:
                        flattened = _flatten_result_data(row.result_data)
                        for key, value in flattened.items():
                            row_data[f"result_{key}"] = value
                    if row.error_message:
                        row_data["error_message"] = row.error_message
                    writer.writerow(row_data)

        job.output_file_path = str(output_path)
        session.add(job)
        session.commit()

        return output_path


def generate_partial_output(job_id: str) -> Path | None:
    """Generate a partial output for download during job processing. Returns a temp file path.
    
    Does NOT set job.output_file_path. Returns a temporary file path that the caller must clean up.
    """
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if job is None:
            return None

        # Check if at least one row has reached terminal state
        rows = session.execute(
            select(JobRow)
            .where(JobRow.job_id == job.id)
            .order_by(JobRow.row_number)
        ).scalars().all()

        if not rows:
            return None

        # Check if any row has reached terminal state
        has_terminal = any(r.status in ("completed", "failed") for r in rows)
        if not has_terminal:
            return None

        # Use the same generation logic but write to a temp file
        input_headers = _get_input_headers(rows)
        result_keys = _get_all_result_keys(rows)

        fieldnames = ["row_number", "status"]
        fieldnames.extend(input_headers)
        fieldnames.extend(result_keys)
        fieldnames.append("error_message")

        output_rows = _build_output_rows(rows, input_headers, result_keys)

        # Create temp file
        suffix = ".xlsx" if job.input_format == "xlsx" else ".csv"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            temp_path = Path(tmp.name)

        if job.input_format == "xlsx":
            import openpyxl
            wb = openpyxl.Workbook()

            # Sheet 1: Input
            ws_input = wb.active
            ws_input.title = "Input"
            input_fieldnames = ["row_number"] + input_headers
            ws_input.append(input_fieldnames)
            for row in rows:
                row_data = {"row_number": row.row_number}
                if row.input_data:
                    for key in input_headers:
                        row_data[key] = row.input_data.get(key, "")
                ws_input.append([row_data.get(key, "") for key in input_fieldnames])

            # Sheet 2: Output
            ws_output = wb.create_sheet("Output")
            output_fieldnames = ["row_number", "status"] + input_headers + _get_all_result_keys(rows) + ["error_message"]
            ws_output.append(output_fieldnames)
            for row in rows:
                row_data = {"row_number": row.row_number, "status": row.status}
                if row.input_data:
                    for key in input_headers:
                        row_data[key] = row.input_data.get(key, "")
                if row.result_data:
                    flattened = _flatten_result_data(row.result_data)
                    for key, value in flattened.items():
                        row_data[f"result_{key}"] = value
                if row.error_message:
                    row_data["error_message"] = row.error_message
                ws_output.append([row_data.get(key, "") for key in output_fieldnames])

            wb.save(temp_path)
        else:
            with temp_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row_data in output_rows:
                    writer.writerow(row_data)

        return temp_path