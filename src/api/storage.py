from __future__ import annotations

import os
import re
from pathlib import Path
from uuid import uuid4

UPLOAD_ROOT = Path("data/uploads")
OUTPUT_ROOT = Path("data/outputs")

UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)


def sanitize_filename(filename: str) -> str:
    filename = os.path.basename(filename)
    filename = re.sub(r"[^\w\s.-]", "", filename)
    filename = re.sub(r"\s+", "_", filename)
    return filename[:255]


def get_job_upload_dir(job_id: str) -> Path:
    job_dir = UPLOAD_ROOT / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir


def get_job_output_dir(job_id: str) -> Path:
    job_dir = OUTPUT_ROOT / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir


def save_upload_file(job_id: str, original_filename: str, content: bytes) -> Path:
    safe_name = sanitize_filename(original_filename)
    unique_name = f"{uuid4().hex[:8]}_{safe_name}"
    job_dir = get_job_upload_dir(job_id)
    file_path = job_dir / unique_name
    file_path.write_bytes(content)
    return file_path


def get_output_file_path(job_id: str, input_filename: str, input_format: str) -> Path:
    base = Path(input_filename).stem
    base = sanitize_filename(base)
    ext = ".xlsx"
    output_name = f"{base}_enriched{ext}"
    return get_job_output_dir(job_id) / output_name


def resolve_safe_output_path(job_id: str, requested_path: str) -> Path | None:
    requested = Path(requested_path).resolve()
    job_output_dir = get_job_output_dir(job_id).resolve()

    try:
        requested.relative_to(job_output_dir)
    except ValueError:
        return None

    if not requested.exists():
        return None

    return requested