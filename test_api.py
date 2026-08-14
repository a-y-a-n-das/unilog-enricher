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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])