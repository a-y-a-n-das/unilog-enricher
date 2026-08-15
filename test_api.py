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
    assert response.status_code == 409


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
    assert "TAVILY_API_KEY=" in content
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
            assert value == "" or value.startswith("nvidia/") or value == "nvidia" or key == "CORS_ORIGINS" or key == "WORKER_CONCURRENCY", \
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
    expected_pattern = f"enriched_{short_job_id}.csv"
    assert filename == expected_pattern, f"Expected {expected_pattern}, got {filename}"
    
    # Verify no user-provided filename parts in download name
    assert "test" not in filename.lower(), "Should not contain original filename"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])