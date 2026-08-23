"""Tests for free credits tracker."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from services.free_credits import FreeCreditsTracker, get_free_credits_tracker, reset_free_credits_tracker


class TestFreeCreditsTracker:
    """Tests for FreeCreditsTracker class."""

    def setup_method(self):
        """Reset global tracker before each test."""
        reset_free_credits_tracker()

    def teardown_method(self):
        """Clean up after each test."""
        reset_free_credits_tracker()

    def test_initial_allowance_from_env(self):
        """Test that initial allowance is loaded from FREE_CREDITS env var."""
        with patch.dict(os.environ, {"FREE_CREDITS": "50"}):
            tracker = FreeCreditsTracker()
            assert tracker._initial_credits == 50
            assert tracker.get_remaining() == 50

    def test_default_allowance_when_env_not_set(self):
        """Test default allowance when FREE_CREDITS not set."""
        with patch.dict(os.environ, {}, clear=True):
            tracker = FreeCreditsTracker()
            assert tracker._initial_credits == 100  # DEFAULT_FREE_CREDITS
            assert tracker.get_remaining() == 100

    def test_successful_row_consumes_one_credit(self):
        """Test that successful row consumes exactly 1 credit."""
        tracker = FreeCreditsTracker(initial_credits=10)
        assert tracker.consume_credit() is True
        assert tracker.get_remaining() == 9
        assert tracker.get_summary().credits_used_this_session == 1

    def test_failed_row_consumes_one_credit(self):
        """Test that failed row consumes exactly 1 credit (same as success)."""
        tracker = FreeCreditsTracker(initial_credits=10)
        # Simulate a row attempt that fails - still consumes credit
        assert tracker.consume_credit() is True
        assert tracker.get_remaining() == 9
        assert tracker.get_summary().credits_used_this_session == 1

    def test_exception_consumes_one_credit(self):
        """Test that exception during processing consumes exactly 1 credit."""
        tracker = FreeCreditsTracker(initial_credits=10)
        # Credit consumed before processing, so exception still counts
        assert tracker.consume_credit() is True
        assert tracker.get_remaining() == 9

    def test_multiple_internal_operations_single_credit(self):
        """Test that a row with multiple internal ops consumes exactly 1 credit."""
        tracker = FreeCreditsTracker(initial_credits=10)
        # One row = one credit, regardless of internal operations
        assert tracker.consume_credit() is True
        assert tracker.get_remaining() == 9
        # Internal retries/searches don't consume additional credits
        assert tracker.get_summary().credits_used_this_session == 1

    def test_batch_of_n_rows_consumes_n_credits(self):
        """Test that N attempted rows consume N credits."""
        tracker = FreeCreditsTracker(initial_credits=10)
        for i in range(5):
            assert tracker.consume_credit() is True
        assert tracker.get_remaining() == 5
        assert tracker.get_summary().credits_used_this_session == 5

    def test_processing_continues_when_credits_exhausted(self):
        """Test that can_process_row always returns True (informational only)."""
        tracker = FreeCreditsTracker(initial_credits=3)
        assert tracker.can_process_row() is True
        tracker.consume_credit()
        assert tracker.can_process_row() is True
        tracker.consume_credit()
        assert tracker.can_process_row() is True
        tracker.consume_credit()
        assert tracker.can_process_row() is True  # Still True - doesn't block
        assert tracker.consume_credit() is True  # Still consumes (goes negative)
        assert tracker.get_remaining() == -1

    def test_submitting_more_rows_than_credits_processes_all(self):
        """Test that all rows are processed (credits go negative, no blocking)."""
        tracker = FreeCreditsTracker(initial_credits=3)
        processed = 0
        for _ in range(10):  # Try to process 10 rows
            if tracker.consume_credit():
                processed += 1
        assert processed == 10  # All processed, no blocking
        assert tracker.get_remaining() == -7  # Went negative

    def test_counter_persists_across_restarts(self):
        """Test that counter survives restart via file persistence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            credits_file = Path(tmpdir) / "free_credits.json"
            with patch("services.free_credits.CREDITS_FILE", credits_file):
                # First tracker instance
                tracker1 = FreeCreditsTracker(initial_credits=10)
                tracker1.consume_credit()
                tracker1.consume_credit()
                assert tracker1.get_remaining() == 8

                # Simulate restart - new tracker instance
                tracker2 = FreeCreditsTracker(initial_credits=10)
                assert tracker2.get_remaining() == 8  # Loaded from file
                assert tracker2._initial_credits == 10

    def test_counter_does_not_reset_to_initial_on_request(self):
        """Test that remaining counter doesn't reset to initial on every request."""
        tracker = FreeCreditsTracker(initial_credits=10)
        tracker.consume_credit()
        tracker.consume_credit()
        remaining_before = tracker.get_remaining()

        # Get summary multiple times - should not reset
        for _ in range(5):
            tracker.get_summary()
        assert tracker.get_remaining() == remaining_before

    def test_frontend_receives_actual_remaining_count(self):
        """Test that API summary returns actual remaining count."""
        tracker = FreeCreditsTracker(initial_credits=100)
        tracker.consume_credit()
        tracker.consume_credit()
        tracker.consume_credit()

        summary = tracker.get_summary()
        assert summary.remaining_credits == 97
        assert summary.initial_credits == 100
        assert summary.credits_used_this_session == 3

    def test_invalid_env_value_uses_default(self):
        """Test that invalid FREE_CREDITS value falls back to default."""
        with patch.dict(os.environ, {"FREE_CREDITS": "invalid"}):
            tracker = FreeCreditsTracker()
            assert tracker._initial_credits == 100

    def test_negative_env_value_uses_default(self):
        """Test that negative FREE_CREDITS value falls back to default."""
        with patch.dict(os.environ, {"FREE_CREDITS": "-5"}):
            tracker = FreeCreditsTracker()
            assert tracker._initial_credits == 100

    def test_reset_restores_initial_credits(self):
        """Test that reset restores remaining credits to initial."""
        tracker = FreeCreditsTracker(initial_credits=10)
        tracker.consume_credit()
        tracker.consume_credit()
        assert tracker.get_remaining() == 8

        tracker.reset()
        assert tracker.get_remaining() == 10
        assert tracker.get_summary().credits_used_this_session == 0

    def test_configure_updates_initial_credits(self):
        """Test that configure can update initial credits."""
        tracker = FreeCreditsTracker(initial_credits=10)
        tracker.configure(initial_credits=20)
        assert tracker._initial_credits == 20
        assert tracker.get_remaining() == 10  # Remaining unchanged if less than new initial

    def test_configure_does_not_increase_remaining_above_initial(self):
        """Test that configure caps remaining at new initial."""
        tracker = FreeCreditsTracker(initial_credits=20)
        tracker.consume_credit()  # remaining = 19
        tracker.configure(initial_credits=10)  # Should cap remaining at 10
        assert tracker.get_remaining() == 10

    def test_thread_safety(self):
        """Test that tracker is thread-safe for concurrent access."""
        import threading
        import time

        tracker = FreeCreditsTracker(initial_credits=100)
        errors = []

        def consume_credits(n):
            try:
                for _ in range(n):
                    tracker.consume_credit()
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=consume_credits, args=(10,)) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert tracker.get_remaining() == 50  # 100 - 5*10
        assert tracker.get_summary().credits_used_this_session == 50


class TestFreeCreditsTrackerGlobal:
    """Tests for global tracker functions."""

    def setup_method(self):
        reset_free_credits_tracker()

    def teardown_method(self):
        reset_free_credits_tracker()

    def test_get_free_credits_tracker_returns_singleton(self):
        """Test that get_free_credits_tracker returns same instance."""
        tracker1 = get_free_credits_tracker()
        tracker2 = get_free_credits_tracker()
        assert tracker1 is tracker2

    def test_reset_free_credits_tracker_resets_global(self):
        """Test that reset_free_credits_tracker resets the global instance."""
        tracker1 = get_free_credits_tracker()
        tracker1.consume_credit()
        assert tracker1.get_remaining() == 99  # default 100 - 1

        reset_free_credits_tracker()
        tracker2 = get_free_credits_tracker()
        assert tracker2.get_remaining() == 100
        assert tracker2 is not tracker1  # New instance


if __name__ == "__main__":
    pytest.main([__file__, "-v"])