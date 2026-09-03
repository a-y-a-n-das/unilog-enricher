#!/usr/bin/env python
"""
Integration tests for the FastAPI API layer (mocked worker).
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.routes import get_processing_service, get_worker
from api.storage import UPLOAD_ROOT, OUTPUT_ROOT
from services.processing_service import ProcessingService
from services.worker import Worker


client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock the ProcessingService and Worker dependencies."""
    mock_processing_service = MagicMock(spec=ProcessingService)
    mock_worker = MagicMock(spec=Worker)
    
    app.dependency_overrides[get_processing_service] = lambda: mock_processing_service
    app.dependency_overrides[get_worker] = lambda: mock_worker
    
    yield mock_worker
    
    app.dependency_overrides.clear()


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_upload_valid_csv(mock_dependencies):
    csv_content = """product_name,brand,category
Apple iPhone 15,Apple,Smartphones
Samsung Galaxy S24,Samsung,Smartphones
Sony WH-1000XM5,Sony,Headphones
"""
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    response = client.post("/api/jobs", files=files)
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    assert data["total_rows"] == 3
    mock_dependencies.run_job.assert_called_once()
    return data["job_id"]


def test_upload_valid_xlsx(mock_dependencies):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Input"
    ws.append(["product_name", "brand", "category"])
    ws.append(["Apple iPhone 15", "Apple", "Smartphones"])
    ws.append(["Samsung Galaxy S24", "Samsung", "Smartphones"])
    ws.append(["Sony WH-1000XM5", "Sony", "Headphones"])

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        wb.save(f.name)
        with open(f.name, "rb") as xlsx_file:
            files = {"file": ("test.xlsx", xlsx_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            response = client.post("/api/jobs", files=files)

    Path(f.name).unlink(missing_ok=True)

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    assert data["total_rows"] == 3
    return data["job_id"]


def test_upload_invalid_extension(mock_dependencies):
    files = {"file": ("test.txt", io.BytesIO(b"test"), "text/plain")}
    response = client.post("/api/jobs", files=files)
    assert response.status_code == 415
    assert "Unsupported file format" in response.json()["detail"]


def test_upload_empty_file(mock_dependencies):
    files = {"file": ("empty.csv", io.BytesIO(b""), "text/csv")}
    response = client.post("/api/jobs", files=files)
    assert response.status_code == 400
    assert "Empty file" in response.json()["detail"]


def test_upload_duplicate_header(mock_dependencies):
    csv_content = """product_name,product_name,category
Apple iPhone 15,Apple,Smartphones
"""
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    response = client.post("/api/jobs", files=files)
    assert response.status_code == 400
    assert "Duplicate column header: product_name" in response.json()["detail"]


def test_upload_empty_header(mock_dependencies):
    csv_content = """product_name,,category
Apple iPhone 15,Apple,Smartphones
"""
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    response = client.post("/api/jobs", files=files)
    assert response.status_code == 400
    assert "empty column header" in response.json()["detail"]


def test_upload_header_only(mock_dependencies):
    csv_content = """product_name,brand,category
"""
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    response = client.post("/api/jobs", files=files)
    assert response.status_code == 400
    assert "No valid data rows" in response.json()["detail"]


def test_upload_missing_xlsx_sheet(mock_dependencies):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "WrongSheet"
    ws.append(["product_name", "brand", "category"])
    ws.append(["Apple iPhone 15", "Apple", "Smartphones"])

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        wb.save(f.name)
        with open(f.name, "rb") as xlsx_file:
            files = {"file": ("test.xlsx", xlsx_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            response = client.post("/api/jobs", files=files)

    Path(f.name).unlink(missing_ok=True)

    assert response.status_code == 400
    assert "must contain a 'Input' sheet" in response.json()["detail"]


def test_get_job_status(mock_dependencies):
    job_id = test_upload_valid_csv(mock_dependencies)

    response = client.get(f"/api/jobs/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job_id
    assert data["status"] == "queued"
    assert data["total_rows"] == 3
    assert data["processed_rows"] == 0
    assert data["successful_rows"] == 0
    assert data["failed_rows"] == 0
    assert "created_at" in data
    assert "output_available" in data


def test_get_job_rows(mock_dependencies):
    job_id = test_upload_valid_csv(mock_dependencies)

    response = client.get(f"/api/jobs/{job_id}/rows")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[0]["row_number"] == 2
    assert data[1]["row_number"] == 3
    assert data[2]["row_number"] == 4
    for row in data:
        assert row["status"] == "pending"
        assert row["attempts"] == 0


def test_get_nonexistent_job():
    response = client.get("/api/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_get_nonexistent_job_rows():
    response = client.get("/api/jobs/00000000-0000-0000-0000-000000000000/rows")
    assert response.status_code == 404


def test_download_missing_output(mock_dependencies):
    job_id = test_upload_valid_csv(mock_dependencies)
    response = client.get(f"/api/jobs/{job_id}/download")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def test_path_traversal_blocked(mock_dependencies):
    job_id = test_upload_valid_csv(mock_dependencies)

    from api.storage import resolve_safe_output_path
    result = resolve_safe_output_path(job_id, "/etc/passwd")
    assert result is None

    result = resolve_safe_output_path(job_id, "../../etc/passwd")
    assert result is None


def test_upload_1000_rows(mock_dependencies):
    """Test uploading a CSV with 1000 valid data rows."""
    import csv
    from io import StringIO

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["product_name", "brand", "category", "sku"])
    
    for i in range(1000):
        writer.writerow([f"Product {i}", f"Brand {i % 10}", f"Category {i % 5}", f"SKU-{i:04d}"])
    
    csv_content = output.getvalue()
    
    files = {"file": ("test_1000.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    response = client.post("/api/jobs", files=files)
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    assert data["total_rows"] == 1000

    job_id = data["job_id"]

    # Verify Job and JobRows created correctly in database
    from database import repositories
    job = repositories.get_job(job_id)
    assert job is not None
    assert job.total_rows == 1000
    assert job.status == "queued"

    # Verify JobRows
    from database.connection import SessionLocal
    from database.models import JobRow
    from sqlalchemy import select
    with SessionLocal() as session:
        rows = session.execute(
            select(JobRow).where(JobRow.job_id == job.id).order_by(JobRow.row_number)
        ).scalars().all()
        assert len(rows) == 1000
        for row in rows:
            assert row.status == "pending"
            assert row.attempts == 0
            assert "product_name" in row.input_data.get("data", row.input_data)

    mock_dependencies.run_job.assert_called_once()
    print(f"1000-row test passed: job_id={job_id}")


def test_env_example_exists():
    """Test that .env.example exists and contains no real secrets."""
    from pathlib import Path
    env_example = Path(".env.example")
    assert env_example.exists(), ".env.example should exist"
    
    content = env_example.read_text()
    assert "NVIDIA_API_KEY=" in content
    assert "FIRECRAWL_API_KEY=" in content
    assert "EXA_API_KEY=" in content
    assert "FREE_CREDITS=" in content
    assert "DATABASE_URL=" in content
    assert "LLM_PROVIDER=" in content
    assert "LLM_MODEL=" in content
    
    # Verify no real secrets (no actual API key values)
    lines = content.strip().split('\n')
    for line in lines:
        if '=' in line:
            key, value = line.split('=', 1)
            # Values should be empty or placeholders only
            # CORS_ORIGINS is allowed to have placeholder URLs
            # WORKER_CONCURRENCY is allowed to have numeric values
            # FREE_CREDITS is allowed to have numeric values
            # EXA_MONTHLY_DOLLAR_LIMIT is allowed to have numeric values
            assert value == "" or value.startswith("nvidia/") or value == "nvidia" or key == "CORS_ORIGINS" or key == "WORKER_CONCURRENCY" or key == "FREE_CREDITS" or key == "EXA_MONTHLY_DOLLAR_LIMIT", \
                f"Unexpected value for {key}: {value}"


def test_upload_size_limit(mock_dependencies):
    """Test that oversized uploads are rejected with HTTP 413."""
    # Create content larger than 50MB
    large_content = b"x" * (51 * 1024 * 1024)  # 51 MB
    files = {"file": ("large.csv", io.BytesIO(large_content), "text/csv")}
    
    # TestClient doesn't trigger middleware by default, so we test the middleware directly
    # by making a request with a Content-Length header
    from starlette.testclient import TestClient
    from api.app import app
    
    test_client = TestClient(app, raise_server_exceptions=False)
    
    # Test with Content-Length header indicating oversized upload
    headers = {"Content-Length": str(51 * 1024 * 1024)}
    files = {"file": ("large.csv", io.BytesIO(b"small content"), "text/csv")}
    
    # We need to test the middleware directly
    import httpx
    transport = httpx.ASGITransport(app=app)
    async_client = httpx.AsyncClient(transport=transport, base_url="http://test")
    
    import asyncio
    
    async def test_oversized():
        response = await async_client.post(
            "/api/jobs",
            files={"file": ("large.csv", io.BytesIO(b"x" * 100), "text/csv")},
            headers={"Content-Length": str(51 * 1024 * 1024)}
        )
        return response
    
    response = asyncio.run(test_oversized())
    assert response.status_code == 413
    assert "too large" in response.json()["detail"].lower()


def test_cors_configuration():
    """Test that CORS is configured from CORS_ORIGINS environment variable."""
    from api.app import app, get_cors_origins
    from fastapi.middleware.cors import CORSMiddleware
    import os
    
    # Find the CORS middleware
    cors_middleware = None
    for middleware in app.user_middleware:
        if middleware.cls == CORSMiddleware:
            cors_middleware = middleware
            break
    
    assert cors_middleware is not None, "CORS middleware should be configured"
    
    # Check options - they're stored in middleware.kwargs
    options = cors_middleware.kwargs
    assert options.get("allow_credentials") is False, \
        "allow_credentials should be False"
    
    # Verify the middleware has allow_origins configured (may be set from .env in test environment)
    allow_origins = options.get("allow_origins")
    assert isinstance(allow_origins, list), "allow_origins should be a list"
    
    # Test get_cors_origins function
    os.environ["CORS_ORIGINS"] = "http://localhost:5173,https://example.com"
    try:
        origins = get_cors_origins()
        assert origins == ["http://localhost:5173", "https://example.com"]
    finally:
        del os.environ["CORS_ORIGINS"]
    
    # Test empty CORS_ORIGINS
    os.environ["CORS_ORIGINS"] = ""
    try:
        origins = get_cors_origins()
        assert origins == []
    finally:
        del os.environ["CORS_ORIGINS"]


def test_nvidia_client_no_debug_output(mock_dependencies):
    """Test that NVIDIA client no longer prints debug output unconditionally."""
    from pipeline.llm.nvidia import NVIDIAClient
    import inspect
    
    # Check that generate method doesn't have print statements for content/reasoning
    source = inspect.getsource(NVIDIAClient.generate)
    
    # Should not contain print of content or reasoning
    assert "print(" not in source or "LLM RESPONSE DEBUG" not in source, \
        "NVIDIAClient.generate should not have debug print statements"
    
    # Should not contain content or reasoning logging
    assert "choice.message.content" not in source, \
        "Should not log full response content"
    assert "choice.message.reasoning_content" not in source, \
        "Should not log reasoning content"
    
    # Should still have max_retries=5
    source_init = inspect.getsource(NVIDIAClient.__init__)
    assert "max_retries=5" in source_init, \
        "max_retries should remain 5"


def test_download_filename_deterministic(mock_dependencies):
    """Test that download filename is deterministic and safe."""
    from database import repositories
    from database.connection import SessionLocal
    from database.models import Job
    from models.input_models import InputRecord
    from services.job_service import create_job
    from api.output_generator import generate_output
    from unittest.mock import MagicMock
    from pipeline.ingestion.web_scraper import WebScraper
    
    # Create a test job
    records = [
        InputRecord(row_number=1, data={"product_name": "Test Product"})
    ]
    job = create_job(
        input_filename="test.csv",
        input_format="csv",
        input_file_path="/tmp/test.csv",
        rows=records,
    )
    
    # Mock worker and generate output
    from services.processing_service import ProcessingService, ProcessingResult, ProcessingTimings
    mock_result = ProcessingResult(
        record=records[0],
        product={"name": "Test"},
        timings=ProcessingTimings(research_seconds=1.0, evidence_seconds=0.5, extraction_seconds=0.3, total_seconds=1.8)
    )
    mock_ps = MagicMock(spec=ProcessingService)
    mock_ps.process.return_value = mock_result
    
    from services.worker import Worker
    worker = Worker(mock_ps)
    worker.run_job(str(job.id))
    
    # Test download endpoint
    from fastapi.testclient import TestClient
    client = TestClient(app)
    
    response = client.get(f"/api/jobs/{job.id}/download")
    assert response.status_code == 200
    
    # Check Content-Disposition header
    content_disposition = response.headers.get("content-disposition", "")
    assert "attachment; filename=" in content_disposition
    
    # Extract filename
    import re
    match = re.search(r'filename="([^"]+)"', content_disposition)
    assert match, "Filename should be in Content-Disposition header"
    filename = match.group(1)
    
    # Filename should follow pattern: enriched_<8-char-job-id>.<ext>
    short_job_id = str(job.id)[:8]
    expected_pattern = f"enriched_{short_job_id}.xlsx"
    assert filename == expected_pattern, f"Expected {expected_pattern}, got {filename}"
    
    # Verify no user-provided filename parts in download name
    assert "test" not in filename.lower(), "Should not contain original filename"


def test_repository_get_recoverable_jobs():
    """Test that get_recoverable_jobs finds queued and processing jobs with pending/processing rows."""
    from database import repositories
    from database.connection import SessionLocal
    from database.models import Job, JobRow
    from models.input_models import InputRecord
    from services.job_service import create_job
    import uuid

    # Create a queued job with pending rows
    records = [
        InputRecord(row_number=1, data={"product_name": "Product 1"}),
        InputRecord(row_number=2, data={"product_name": "Product 2"}),
    ]
    queued_job = create_job(
        input_filename="test_queued.csv",
        input_format="csv",
        input_file_path="/tmp/test_queued.csv",
        rows=records,
    )

    # Create a processing job with mixed row statuses
    processing_job = create_job(
        input_filename="test_processing.csv",
        input_format="csv",
        input_file_path="/tmp/test_processing.csv",
        rows=[
            InputRecord(row_number=1, data={"product_name": "Product A"}),
            InputRecord(row_number=2, data={"product_name": "Product B"}),
            InputRecord(row_number=3, data={"product_name": "Product C"}),
        ],
    )
    # Manually set job to processing and rows to mixed statuses
    with SessionLocal() as session:
        job = session.get(Job, processing_job.id)
        job.status = "processing"
        job.started_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        
        rows = session.execute(
            __import__("sqlalchemy").select(JobRow).where(JobRow.job_id == processing_job.id).order_by(JobRow.row_number)
        ).scalars().all()
        
        # Row 1: completed
        rows[0].status = "completed"
        rows[0].completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        # Row 2: processing (stuck)
        rows[1].status = "processing"
        rows[1].attempts = 1
        rows[1].started_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        # Row 3: pending
        rows[2].status = "pending"
        
        session.commit()

    # Create a completed job (should NOT be recoverable)
    completed_job = create_job(
        input_filename="test_completed.csv",
        input_format="csv",
        input_file_path="/tmp/test_completed.csv",
        rows=[
            InputRecord(row_number=1, data={"product_name": "Product X"}),
        ],
    )
    with SessionLocal() as session:
        job = session.get(Job, completed_job.id)
        job.status = "completed"
        job.completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        rows = session.execute(
            __import__("sqlalchemy").select(JobRow).where(JobRow.job_id == completed_job.id)
        ).scalars().all()
        rows[0].status = "completed"
        rows[0].completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        session.commit()

    # Create a failed job (should NOT be recoverable)
    failed_job = create_job(
        input_filename="test_failed.csv",
        input_format="csv",
        input_file_path="/tmp/test_failed.csv",
        rows=[
            InputRecord(row_number=1, data={"product_name": "Product Y"}),
        ],
    )
    with SessionLocal() as session:
        job = session.get(Job, failed_job.id)
        job.status = "failed"
        job.error_message = "Some error"
        rows = session.execute(
            __import__("sqlalchemy").select(JobRow).where(JobRow.job_id == failed_job.id)
        ).scalars().all()
        rows[0].status = "failed"
        rows[0].completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        session.commit()

    # Test get_recoverable_jobs
    recoverable = repositories.get_recoverable_jobs()
    recoverable_ids = {str(j.id) for j in recoverable}

    assert str(queued_job.id) in recoverable_ids, "Queued job with pending rows should be recoverable"
    assert str(processing_job.id) in recoverable_ids, "Processing job with pending/processing rows should be recoverable"
    assert str(completed_job.id) not in recoverable_ids, "Completed job should not be recoverable"
    assert str(failed_job.id) not in recoverable_ids, "Failed job should not be recoverable"

    print("test_repository_get_recoverable_jobs passed")


def test_repository_reset_processing_rows():
    """Test that reset_processing_rows resets processing rows to pending and preserves attempts."""
    from database import repositories
    from database.connection import SessionLocal
    from database.models import Job, JobRow
    from models.input_models import InputRecord
    from services.job_service import create_job

    job = create_job(
        input_filename="test_reset.csv",
        input_format="csv",
        input_file_path="/tmp/test_reset.csv",
        rows=[
            InputRecord(row_number=1, data={"product_name": "Product 1"}),
            InputRecord(row_number=2, data={"product_name": "Product 2"}),
            InputRecord(row_number=3, data={"product_name": "Product 3"}),
        ],
    )

    # Set up mixed row statuses
    with SessionLocal() as session:
        rows = session.execute(
            __import__("sqlalchemy").select(JobRow).where(JobRow.job_id == job.id).order_by(JobRow.row_number)
        ).scalars().all()
        
        # Row 1: completed (should NOT be reset)
        rows[0].status = "completed"
        rows[0].completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        # Row 2: processing with attempts=2 (should be reset to pending, attempts preserved)
        rows[1].status = "processing"
        rows[1].attempts = 2
        rows[1].started_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        # Row 3: pending (should NOT be reset)
        rows[2].status = "pending"
        
        session.commit()

    # Reset processing rows
    reset_count = repositories.reset_processing_rows(job.id)
    assert reset_count == 1, "Should reset exactly 1 row"

    # Verify results
    with SessionLocal() as session:
        rows = session.execute(
            __import__("sqlalchemy").select(JobRow).where(JobRow.job_id == job.id).order_by(JobRow.row_number)
        ).scalars().all()
        
        # Row 1: still completed
        assert rows[0].status == "completed"
        # Row 2: reset to pending, attempts preserved
        assert rows[1].status == "pending"
        assert rows[1].attempts == 2, "Attempts should be preserved"
        assert rows[1].started_at is None, "started_at should be cleared"
        # Row 3: still pending
        assert rows[2].status == "pending"
        assert rows[2].attempts == 0

    print("test_repository_reset_processing_rows passed")


def test_repository_reset_job_for_recovery():
    """Test that reset_job_for_recovery resets job status to queued and clears started_at."""
    from database import repositories
    from database.connection import SessionLocal
    from database.models import Job
    from models.input_models import InputRecord
    from services.job_service import create_job
    import datetime

    job = create_job(
        input_filename="test_reset_job.csv",
        input_format="csv",
        input_file_path="/tmp/test_reset_job.csv",
        rows=[
            InputRecord(row_number=1, data={"product_name": "Product 1"}),
        ],
    )

    # Set job to processing with started_at
    with SessionLocal() as session:
        j = session.get(Job, job.id)
        j.status = "processing"
        j.started_at = datetime.datetime.now(datetime.timezone.utc)
        session.commit()

    # Reset job for recovery
    reset_job = repositories.reset_job_for_recovery(job.id)
    assert reset_job is not None
    assert reset_job.status == "queued"
    assert reset_job.started_at is None
    # completed_at should remain None (not set yet)
    assert reset_job.completed_at is None

    print("test_repository_reset_job_for_recovery passed")


def test_recovery_preserves_completed_rows():
    """Test that recovery does not affect completed rows."""
    from database import repositories
    from database.connection import SessionLocal
    from database.models import Job, JobRow
    from models.input_models import InputRecord
    from services.job_service import create_job
    import datetime

    job = create_job(
        input_filename="test_preserve.csv",
        input_format="csv",
        input_file_path="/tmp/test_preserve.csv",
        rows=[
            InputRecord(row_number=1, data={"product_name": "Product 1"}),
            InputRecord(row_number=2, data={"product_name": "Product 2"}),
        ],
    )

    # Set up: row 1 completed, row 2 processing
    with SessionLocal() as session:
        j = session.get(Job, job.id)
        j.status = "processing"
        j.started_at = datetime.datetime.now(datetime.timezone.utc)
        
        rows = session.execute(
            __import__("sqlalchemy").select(JobRow).where(JobRow.job_id == job.id).order_by(JobRow.row_number)
        ).scalars().all()
        
        rows[0].status = "completed"
        rows[0].completed_at = datetime.datetime.now(datetime.timezone.utc)
        rows[0].result_data = {"name": "Product 1"}
        
        rows[1].status = "processing"
        rows[1].attempts = 1
        rows[1].started_at = datetime.datetime.now(datetime.timezone.utc)
        
        session.commit()

    # Run recovery steps
    repositories.reset_processing_rows(job.id)
    repositories.reset_job_for_recovery(job.id)

    # Verify completed row untouched, processing row reset
    with SessionLocal() as session:
        rows = session.execute(
            __import__("sqlalchemy").select(JobRow).where(JobRow.job_id == job.id).order_by(JobRow.row_number)
        ).scalars().all()
        
        assert rows[0].status == "completed"
        assert rows[0].result_data == {"name": "Product 1"}
        assert rows[1].status == "pending"
        assert rows[1].attempts == 1  # preserved

    print("test_recovery_preserves_completed_rows passed")


def test_repository_get_recoverable_jobs_excludes_jobs_without_pending_rows():
    """Test that jobs with only completed/failed rows are not recoverable."""
    from database import repositories
    from database.connection import SessionLocal
    from database.models import Job, JobRow
    from models.input_models import InputRecord
    from services.job_service import create_job

    # Job with all rows completed
    job_completed = create_job(
        input_filename="test_all_completed.csv",
        input_format="csv",
        input_file_path="/tmp/test_all_completed.csv",
        rows=[
            InputRecord(row_number=1, data={"product_name": "Product 1"}),
        ],
    )
    with SessionLocal() as session:
        j = session.get(Job, job_completed.id)
        j.status = "queued"  # still queued but all rows done
        rows = session.execute(
            __import__("sqlalchemy").select(JobRow).where(JobRow.job_id == job_completed.id)
        ).scalars().all()
        rows[0].status = "completed"
        rows[0].completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        session.commit()

    # Job with all rows failed
    job_failed = create_job(
        input_filename="test_all_failed.csv",
        input_format="csv",
        input_file_path="/tmp/test_all_failed.csv",
        rows=[
            InputRecord(row_number=1, data={"product_name": "Product 1"}),
        ],
    )
    with SessionLocal() as session:
        j = session.get(Job, job_failed.id)
        j.status = "processing"
        rows = session.execute(
            __import__("sqlalchemy").select(JobRow).where(JobRow.job_id == job_failed.id)
        ).scalars().all()
        rows[0].status = "failed"
        rows[0].completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        session.commit()

    recoverable = repositories.get_recoverable_jobs()
    recoverable_ids = {str(j.id) for j in recoverable}

    assert str(job_completed.id) not in recoverable_ids, "Job with all completed rows should not be recoverable"
    assert str(job_failed.id) not in recoverable_ids, "Job with all failed rows should not be recoverable"

    print("test_repository_get_recoverable_jobs_excludes_jobs_without_pending_rows passed")


def test_retry_failed_rows_endpoint():
    """Test retry-failed endpoint requeues failed rows and resets job status."""
    from database import repositories
    from database.connection import SessionLocal
    from database.models import Job, JobRow
    from models.input_models import InputRecord
    from services.job_service import create_job
    from api.app import app
    from fastapi.testclient import TestClient
    from unittest.mock import patch, MagicMock

    client = TestClient(app)

    # Create a job with some rows
    records = [
        InputRecord(row_number=1, data={"product_name": "Product 1"}),
        InputRecord(row_number=2, data={"product_name": "Product 2"}),
        InputRecord(row_number=3, data={"product_name": "Product 3"}),
    ]
    job = create_job(
        input_filename="test_retry.csv",
        input_format="csv",
        input_file_path="/tmp/test_retry.csv",
        rows=records,
    )
    job_id = str(job.id)

    # Manually set rows to failed
    with SessionLocal() as session:
        rows = session.execute(
            __import__("sqlalchemy").select(JobRow).where(JobRow.job_id == job.id).order_by(JobRow.row_number)
        ).scalars().all()

        # Row 1: completed
        rows[0].status = "completed"
        rows[0].completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        rows[0].result_data = {"name": "Product 1"}

        # Row 2: failed with attempts=1
        rows[1].status = "failed"
        rows[1].attempts = 1
        rows[1].error_message = "Original error"
        rows[1].completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

        # Row 3: failed with attempts=2
        rows[2].status = "failed"
        rows[2].attempts = 2
        rows[2].error_message = "Another error"
        rows[2].completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

        session.commit()

    # Set job status to failed
    with SessionLocal() as session:
        j = session.get(Job, job.id)
        j.status = "failed"
        j.error_message = "Job failed"
        session.commit()

    # Mock the Worker to prevent background task from running real processing
    with patch("api.routes.Worker") as mock_worker_class:
        mock_worker = MagicMock()
        mock_worker_class.return_value = mock_worker

        # Call retry-failed endpoint
        response = client.post(f"/api/jobs/{job_id}/retry-failed")
        assert response.status_code == 200
        data = response.json()
        assert data["retried_count"] == 2
        assert "2 failed row(s) requeued" in data["message"]

    # Verify rows: completed unchanged, failed -> pending, attempts preserved, error preserved
    with SessionLocal() as session:
        rows = session.execute(
            __import__("sqlalchemy").select(JobRow).where(JobRow.job_id == job.id).order_by(JobRow.row_number)
        ).scalars().all()

        # Row 1: still completed
        assert rows[0].status == "completed"
        assert rows[0].result_data == {"name": "Product 1"}

        # Row 2: reset to pending, attempts preserved, error preserved
        assert rows[1].status == "pending"
        assert rows[1].attempts == 1
        assert rows[1].error_message == "Original error"
        assert rows[1].started_at is None
        assert rows[1].completed_at is None

        # Row 3: reset to pending, attempts preserved, error preserved
        assert rows[2].status == "pending"
        assert rows[2].attempts == 2
        assert rows[2].error_message == "Another error"
        assert rows[2].started_at is None
        assert rows[2].completed_at is None

    # Verify job status reset to queued
    with SessionLocal() as session:
        j = session.get(Job, job.id)
        assert j.status == "queued"
        assert j.started_at is None
        assert j.completed_at is None
        assert j.error_message is None

    print("test_retry_failed_rows_endpoint passed")


def test_retry_failed_rows_completed_job():
    """Test retry-failed on a completed job with failed rows (partial success)."""
    from database import repositories
    from database.connection import SessionLocal
    from database.models import Job, JobRow
    from models.input_models import InputRecord
    from services.job_service import create_job
    from api.app import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    # Create a job
    records = [
        InputRecord(row_number=1, data={"product_name": "Product 1"}),
        InputRecord(row_number=2, data={"product_name": "Product 2"}),
    ]
    job = create_job(
        input_filename="test_retry_completed.csv",
        input_format="csv",
        input_file_path="/tmp/test_retry_completed.csv",
        rows=records,
    )
    job_id = str(job.id)

    # Set row 1 completed, row 2 failed
    with SessionLocal() as session:
        rows = session.execute(
            __import__("sqlalchemy").select(JobRow).where(JobRow.job_id == job.id).order_by(JobRow.row_number)
        ).scalars().all()

        rows[0].status = "completed"
        rows[0].completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        rows[0].result_data = {"name": "Product 1"}

        rows[1].status = "failed"
        rows[1].attempts = 1
        rows[1].error_message = "Timeout"
        rows[1].completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

        # Set job to completed
        j = session.get(Job, job.id)
        j.status = "completed"
        j.completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        session.commit()

    # Call retry-failed endpoint with mocked Worker
    with patch("api.routes.Worker") as mock_worker_class:
        mock_worker = MagicMock()
        mock_worker_class.return_value = mock_worker

        response = client.post(f"/api/jobs/{job_id}/retry-failed")
        assert response.status_code == 200
        data = response.json()
        assert data["retried_count"] == 1

    # Verify job status reset to queued
    with SessionLocal() as session:
        j = session.get(Job, job.id)
        assert j.status == "queued"
        assert j.started_at is None
        assert j.completed_at is None
        assert j.error_message is None

        # Verify row 1 unchanged, row 2 pending
        rows = session.execute(
            __import__("sqlalchemy").select(JobRow).where(JobRow.job_id == job.id).order_by(JobRow.row_number)
        ).scalars().all()
        assert rows[0].status == "completed"
        assert rows[1].status == "pending"
        assert rows[1].attempts == 1
        assert rows[1].error_message == "Timeout"

    print("test_retry_failed_rows_completed_job passed")


def test_retry_failed_rows_queued_job_unchanged():
    """Test retry-failed on queued job doesn't change job status."""
    from database import repositories
    from database.connection import SessionLocal
    from database.models import Job, JobRow
    from models.input_models import InputRecord
    from services.job_service import create_job
    from api.app import app
    from fastapi.testclient import TestClient
    from unittest.mock import patch, MagicMock

    client = TestClient(app)

    # Create a job
    records = [
        InputRecord(row_number=1, data={"product_name": "Product 1"}),
        InputRecord(row_number=2, data={"product_name": "Product 2"}),
    ]
    job = create_job(
        input_filename="test_retry_queued.csv",
        input_format="csv",
        input_file_path="/tmp/test_retry_queued.csv",
        rows=records,
    )
    job_id = str(job.id)

    # Set row 1 completed, row 2 failed
    with SessionLocal() as session:
        rows = session.execute(
            __import__("sqlalchemy").select(JobRow).where(JobRow.job_id == job.id).order_by(JobRow.row_number)
        ).scalars().all()

        rows[0].status = "completed"
        rows[0].completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

        rows[1].status = "failed"
        rows[1].attempts = 1
        rows[1].error_message = "Error"
        rows[1].completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

        # Job stays queued
        session.commit()

    # Call retry-failed endpoint with mocked Worker
    with patch("api.routes.Worker") as mock_worker_class:
        mock_worker = MagicMock()
        mock_worker_class.return_value = mock_worker

        response = client.post(f"/api/jobs/{job_id}/retry-failed")
        assert response.status_code == 200
        data = response.json()
        assert data["retried_count"] == 1

    # Verify job status unchanged (still queued)
    with SessionLocal() as session:
        j = session.get(Job, job.id)
        assert j.status == "queued"
        # started_at should still be None (was never set)
        assert j.started_at is None

        # Verify row 2 reset to pending
        rows = session.execute(
            __import__("sqlalchemy").select(JobRow).where(JobRow.job_id == job.id).order_by(JobRow.row_number)
        ).scalars().all()
        assert rows[1].status == "pending"
        assert rows[1].attempts == 1
        assert rows[1].error_message == "Error"

    print("test_retry_failed_rows_queued_job_unchanged passed")


def test_retry_failed_rows_no_failed_rows():
    """Test retry-failed on job with no failed rows returns 0."""
    from database import repositories
    from database.connection import SessionLocal
    from database.models import Job, JobRow
    from models.input_models import InputRecord
    from services.job_service import create_job
    from api.app import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    # Create a job with all rows completed
    records = [
        InputRecord(row_number=1, data={"product_name": "Product 1"}),
    ]
    job = create_job(
        input_filename="test_retry_none.csv",
        input_format="csv",
        input_file_path="/tmp/test_retry_none.csv",
        rows=records,
    )
    job_id = str(job.id)

    # Set row completed
    with SessionLocal() as session:
        rows = session.execute(
            __import__("sqlalchemy").select(JobRow).where(JobRow.job_id == job.id)
        ).scalars().all()

        rows[0].status = "completed"
        rows[0].completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

        j = session.get(Job, job.id)
        j.status = "completed"
        session.commit()

    # Call retry-failed endpoint
    response = client.post(f"/api/jobs/{job_id}/retry-failed")
    assert response.status_code == 200
    data = response.json()
    assert data["retried_count"] == 0

    # Verify job status unchanged
    with SessionLocal() as session:
        j = session.get(Job, job.id)
        assert j.status == "completed"

    print("test_retry_failed_rows_no_failed_rows passed")


def test_retry_failed_rows_nonexistent_job():
    """Test retry-failed on nonexistent job returns 404."""
    from api.app import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    response = client.post("/api/jobs/00000000-0000-0000-0000-000000000000/retry-failed")
    assert response.status_code == 404

    print("test_retry_failed_rows_nonexistent_job passed")


def test_retry_failed_rows_launches_worker():
    """Test that retry-failed launches a worker when failed rows exist."""
    from database import repositories
    from database.connection import SessionLocal
    from database.models import Job, JobRow
    from models.input_models import InputRecord
    from services.job_service import create_job
    from api.app import app
    from fastapi.testclient import TestClient
    from unittest.mock import MagicMock, patch

    client = TestClient(app)

    # Create a job with failed rows
    records = [
        InputRecord(row_number=1, data={"product_name": "Product 1"}),
        InputRecord(row_number=2, data={"product_name": "Product 2"}),
    ]
    job = create_job(
        input_filename="test_retry_worker.csv",
        input_format="csv",
        input_file_path="/tmp/test_retry_worker.csv",
        rows=records,
    )
    job_id = str(job.id)

    # Set rows to failed
    with SessionLocal() as session:
        rows = session.execute(
            __import__("sqlalchemy").select(JobRow).where(JobRow.job_id == job.id).order_by(JobRow.row_number)
        ).scalars().all()

        rows[0].status = "failed"
        rows[0].attempts = 1
        rows[0].error_message = "Error 1"
        rows[0].completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

        rows[1].status = "failed"
        rows[1].attempts = 1
        rows[1].error_message = "Error 2"
        rows[1].completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

        j = session.get(Job, job.id)
        j.status = "failed"
        session.commit()

    # Mock the Worker to verify it's called
    with patch("api.routes.Worker") as mock_worker_class:
        mock_worker = MagicMock()
        mock_worker_class.return_value = mock_worker

        response = client.post(f"/api/jobs/{job_id}/retry-failed")
        assert response.status_code == 200
        data = response.json()
        assert data["retried_count"] == 2

        # Verify Worker was instantiated and run_job was scheduled
        mock_worker_class.assert_called_once()
        # BackgroundTasks adds the task, but we can't easily verify the exact call
        # The important thing is the endpoint doesn't crash and returns correct response

    # Verify rows were requeued to pending
    with SessionLocal() as session:
        rows = session.execute(
            __import__("sqlalchemy").select(JobRow).where(JobRow.job_id == job.id).order_by(JobRow.row_number)
        ).scalars().all()
        assert rows[0].status == "pending"
        assert rows[1].status == "pending"

    print("test_retry_failed_rows_launches_worker passed")


def test_retry_failed_rows_zero_failed_no_worker():
    """Test that retry-failed does NOT launch worker when no failed rows."""
    from database import repositories
    from database.connection import SessionLocal
    from database.models import Job, JobRow
    from models.input_models import InputRecord
    from services.job_service import create_job
    from api.app import app
    from fastapi.testclient import TestClient
    from unittest.mock import patch

    client = TestClient(app)

    # Create a job with all rows completed
    records = [
        InputRecord(row_number=1, data={"product_name": "Product 1"}),
    ]
    job = create_job(
        input_filename="test_retry_no_worker.csv",
        input_format="csv",
        input_file_path="/tmp/test_retry_no_worker.csv",
        rows=records,
    )
    job_id = str(job.id)

    # Set row completed
    with SessionLocal() as session:
        rows = session.execute(
            __import__("sqlalchemy").select(JobRow).where(JobRow.job_id == job.id)
        ).scalars().all()

        rows[0].status = "completed"
        rows[0].completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

        j = session.get(Job, job.id)
        j.status = "completed"
        session.commit()

    # Mock the Worker to verify it's NOT called
    with patch("api.routes.Worker") as mock_worker_class:
        response = client.post(f"/api/jobs/{job_id}/retry-failed")
        assert response.status_code == 200
        data = response.json()
        assert data["retried_count"] == 0

        # Worker should NOT be instantiated
        mock_worker_class.assert_not_called()

    print("test_retry_failed_rows_zero_failed_no_worker passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])