"""Tests for worker integration with free credits."""

import os
from unittest.mock import MagicMock, patch

import pytest

from database.models import Job, JobRow
from services.free_credits import reset_free_credits_tracker
from services.worker import Worker


class TestWorkerFreeCredits:
    """Tests for worker free credits integration."""

    def setup_method(self):
        """Reset global tracker before each test."""
        reset_free_credits_tracker()

    def teardown_method(self):
        """Clean up after each test."""
        reset_free_credits_tracker()

    @patch("services.worker.repositories")
    @patch("services.worker.get_worker_concurrency", return_value=1)
    def test_worker_stops_when_credits_exhausted(self, mock_concurrency, mock_repos):
        """Test that worker stops processing when credits reach zero."""
        # Setup mock job
        job = MagicMock(spec=Job)
        job.id = "test-job-id"
        job.status = "queued"
        job.started_at = None

        # Create 5 mock rows but only 3 credits
        rows = []
        for i in range(5):
            row = MagicMock(spec=JobRow)
            row.id = f"row-{i}"
            row.row_number = i + 1
            row.input_data = {"data": {"Mfg_Part_Num": f"PART-{i}"}}
            rows.append(row)

        # Track which rows were claimed - return one at a time
        call_count = [0]

        def claim_next_pending_row(job_id):
            if call_count[0] < len(rows):
                row = rows[call_count[0]]
                call_count[0] += 1
                return row
            return None

        mock_repos.get_job.return_value = job
        mock_repos.claim_next_pending_row.side_effect = claim_next_pending_row
        mock_repos.SessionLocal.return_value.__enter__.return_value = MagicMock()

        # Create worker with 3 credits
        with patch.dict(os.environ, {"FREE_CREDITS": "3"}):
            from services.free_credits import get_free_credits_tracker
            tracker = get_free_credits_tracker()
            assert tracker.get_remaining() == 3

            processing_service = MagicMock()
            worker = Worker(processing_service)

            # Run job - should only process 3 rows
            worker.run_job("test-job-id")

            # Verify only 3 rows were processed (credit limit)
            assert processing_service.process.call_count == 3
            assert tracker.get_remaining() == 0

    @patch("services.worker.repositories")
    @patch("services.worker.get_worker_concurrency", return_value=1)
    def test_worker_consumes_credit_before_processing(self, mock_concurrency, mock_repos):
        """Test that credit is consumed at start of row processing."""
        job = MagicMock(spec=Job)
        job.id = "test-job-id"
        job.status = "queued"

        row = MagicMock(spec=JobRow)
        row.id = "row-1"
        row.row_number = 1
        row.input_data = {"data": {"Mfg_Part_Num": "PART-1"}}

        mock_repos.get_job.return_value = job
        mock_repos.claim_next_pending_row.side_effect = [row, None]
        mock_repos.SessionLocal.return_value.__enter__.return_value = MagicMock()

        with patch.dict(os.environ, {"FREE_CREDITS": "1"}):
            from services.free_credits import get_free_credits_tracker
            tracker = get_free_credits_tracker()

            processing_service = MagicMock()
            worker = Worker(processing_service)

            worker.run_job("test-job-id")

            # Credit should be consumed before processing
            assert tracker.get_remaining() == 0
            processing_service.process.assert_called_once()

    @patch("services.worker.repositories")
    @patch("services.worker.get_worker_concurrency", return_value=1)
    def test_failed_row_still_consumes_credit(self, mock_concurrency, mock_repos):
        """Test that failed row still consumes credit."""
        job = MagicMock(spec=Job)
        job.id = "test-job-id"
        job.status = "queued"

        row = MagicMock(spec=JobRow)
        row.id = "row-1"
        row.row_number = 1
        row.input_data = {"data": {"Mfg_Part_Num": "PART-1"}}

        mock_repos.get_job.return_value = job
        mock_repos.claim_next_pending_row.side_effect = [row, None]
        mock_repos.SessionLocal.return_value.__enter__.return_value = MagicMock()

        # Make processing fail
        processing_service = MagicMock()
        processing_service.process.side_effect = Exception("Processing failed")

        with patch.dict(os.environ, {"FREE_CREDITS": "1"}):
            from services.free_credits import get_free_credits_tracker
            tracker = get_free_credits_tracker()

            worker = Worker(processing_service)
            worker.run_job("test-job-id")

            # Credit consumed even though processing failed
            assert tracker.get_remaining() == 0
            assert tracker.get_summary().credits_used_this_session == 1
            mock_repos.mark_row_failed.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])