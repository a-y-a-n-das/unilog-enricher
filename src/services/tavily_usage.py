"""Exa usage tracking service for research capacity estimation."""

import logging
from dataclasses import dataclass
from threading import Lock

from pipeline.llm.config import get_exa_monthly_dollar_limit

LOGGER = logging.getLogger(__name__)


@dataclass
class ExaUsageSummary:
    """Summary of Exa usage for capacity estimation."""

    rows_processed_this_session: int = 0
    estimated_dollars_per_row: float = 0.05
    monthly_dollar_limit: float = 10.0
    actual_dollars_used_this_session: float = 0.0

    @property
    def max_rows_per_month(self) -> int:
        """Maximum rows possible per month based on dollar limit."""
        if self.estimated_dollars_per_row <= 0:
            return 0
        return max(0, int(self.monthly_dollar_limit // self.estimated_dollars_per_row))

    @property
    def estimated_rows_remaining(self) -> int:
        """Estimate rows remaining based on rows processed this session."""
        max_rows = self.max_rows_per_month
        return max(0, max_rows - self.rows_processed_this_session)

    @property
    def actual_rows_remaining(self) -> int:
        """Estimate rows remaining based on actual dollars used."""
        if self.estimated_dollars_per_row <= 0:
            return 0
        return max(0, int((self.monthly_dollar_limit - self.actual_dollars_used_this_session) // self.estimated_dollars_per_row))


class ExaUsageTracker:
    """Thread-safe tracker for Exa API usage across research rows."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._rows_processed_this_session = 0
        self._actual_dollars_used_this_session = 0.0
        self._monthly_limit = 10.0
        self._estimated_dollars_per_row = 0.05

    def configure(
        self,
        monthly_limit: float | None = None,
        estimated_dollars_per_row: float | None = None,
    ) -> None:
        """Configure the tracker with monthly limit and estimated dollars per row."""
        with self._lock:
            if monthly_limit is not None:
                self._monthly_limit = monthly_limit
            if estimated_dollars_per_row is not None:
                self._estimated_dollars_per_row = estimated_dollars_per_row

    def record_row_processed(self) -> None:
        """Record that a row has been processed (successful or failed)."""
        with self._lock:
            self._rows_processed_this_session += 1

    def record_dollars_used(self, dollars: float) -> None:
        """Record actual Exa dollars used."""
        with self._lock:
            self._actual_dollars_used_this_session += dollars

    def record_rows_processed(self, count: int) -> None:
        """Record multiple rows processed at once."""
        with self._lock:
            self._rows_processed_this_session += count

    def get_summary(self) -> dict:
        """Get a summary of current usage for API response."""
        with self._lock:
            rows_processed = self._rows_processed_this_session
            actual_dollars_used = self._actual_dollars_used_this_session
            monthly_limit = self._monthly_limit
            estimated_per_row = self._estimated_dollars_per_row

        max_rows = max(0, int(monthly_limit // estimated_per_row)) if estimated_per_row > 0 else 0
        estimated_rows_remaining = max(0, max_rows - rows_processed)
        actual_rows_remaining = max(0, int((monthly_limit - actual_dollars_used) // estimated_per_row)) if estimated_per_row > 0 else 0

        return {
            "exa": {
                "rows_processed_this_session": rows_processed,
                "actual_dollars_used_this_session": round(actual_dollars_used, 4),
                "estimated_rows_remaining": estimated_rows_remaining,
                "actual_rows_remaining": actual_rows_remaining,
                "max_rows_per_month": max_rows,
                "estimated_dollars_per_row": estimated_per_row,
                "monthly_dollar_limit": monthly_limit,
                "note": (
                    "Row-based estimate: each row consumes ~$0.05 (5 queries × $0.01 per search). "
                    "This is an informational estimate only and does not block processing."
                ),
            }
        }

    def reset(self) -> None:
        """Reset the tracker (useful for testing)."""
        with self._lock:
            self._rows_processed_this_session = 0
            self._actual_dollars_used_this_session = 0.0


# Module-level singleton for cross-request access
_exa_usage_tracker: ExaUsageTracker | None = None


def get_exa_usage_tracker() -> ExaUsageTracker:
    """Get the global Exa usage tracker instance.

    Creates a new tracker on first call with default configuration.
    """
    global _exa_usage_tracker
    if _exa_usage_tracker is None:
        _exa_usage_tracker = ExaUsageTracker()
        _exa_usage_tracker.configure(monthly_limit=10.0)
    return _exa_usage_tracker


def reset_exa_usage_tracker() -> None:
    """Reset the global tracker (useful for testing)."""
    global _exa_usage_tracker
    if _exa_usage_tracker is not None:
        _exa_usage_tracker.reset()