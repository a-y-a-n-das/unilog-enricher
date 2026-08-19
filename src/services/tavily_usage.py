"""Tavily usage tracking service for research capacity estimation."""

import logging
from dataclasses import dataclass
from threading import Lock

from pipeline.llm.config import get_tavily_monthly_credits

LOGGER = logging.getLogger(__name__)


@dataclass
class TavilyUsageSummary:
    """Summary of Tavily usage for capacity estimation."""

    rows_processed_this_session: int = 0
    estimated_credits_per_row: int = 10
    monthly_credit_limit: int = 1000

    @property
    def max_rows_per_month(self) -> int:
        """Maximum rows possible per month based on credit limit."""
        if self.estimated_credits_per_row <= 0:
            return 0
        return max(0, self.monthly_credit_limit // self.estimated_credits_per_row)

    @property
    def estimated_rows_remaining(self) -> int:
        """Estimate rows remaining based on rows processed this session."""
        max_rows = self.max_rows_per_month
        return max(0, max_rows - self.rows_processed_this_session)


class TavilyUsageTracker:
    """Thread-safe tracker for Tavily API usage across research rows."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._rows_processed_this_session = 0
        self._monthly_limit = 1000
        self._estimated_credits_per_row = 10

    def configure(
        self,
        monthly_limit: int | None = None,
        estimated_credits_per_row: int | None = None,
    ) -> None:
        """Configure the tracker with monthly limit and estimated credits per row."""
        with self._lock:
            if monthly_limit is not None:
                self._monthly_limit = monthly_limit
            if estimated_credits_per_row is not None:
                self._estimated_credits_per_row = estimated_credits_per_row

    def record_row_processed(self) -> None:
        """Record that a row has been processed (successful or failed)."""
        with self._lock:
            self._rows_processed_this_session += 1

    def record_rows_processed(self, count: int) -> None:
        """Record multiple rows processed at once."""
        with self._lock:
            self._rows_processed_this_session += count

    def get_summary(self) -> dict:
        """Get a summary of current usage for API response."""
        with self._lock:
            rows_processed = self._rows_processed_this_session
            monthly_limit = self._monthly_limit
            estimated_per_row = self._estimated_credits_per_row

        max_rows = max(0, monthly_limit // estimated_per_row) if estimated_per_row > 0 else 0
        estimated_rows_remaining = max(0, max_rows - rows_processed)

        return {
            "tavily": {
                "rows_processed_this_session": rows_processed,
                "estimated_rows_remaining": estimated_rows_remaining,
                "max_rows_per_month": max_rows,
                "estimated_credits_per_row": estimated_per_row,
                "monthly_credit_limit": monthly_limit,
                "note": (
                    "Row-based estimate: each row consumes ~10 credits (5 queries × 2 credits). "
                    "This is an informational estimate only and does not block processing."
                ),
            }
        }

    def reset(self) -> None:
        """Reset the tracker (useful for testing)."""
        with self._lock:
            self._rows_processed_this_session = 0


# Module-level singleton for cross-request access
_tavily_usage_tracker: TavilyUsageTracker | None = None


def get_tavily_usage_tracker() -> TavilyUsageTracker:
    """Get the global Tavily usage tracker instance.

    Creates a new tracker on first call with default configuration.
    """
    global _tavily_usage_tracker
    if _tavily_usage_tracker is None:
        _tavily_usage_tracker = TavilyUsageTracker()
        _tavily_usage_tracker.configure(monthly_limit=1000)
    return _tavily_usage_tracker


def reset_tavily_usage_tracker() -> None:
    """Reset the global tracker (useful for testing)."""
    global _tavily_usage_tracker
    if _tavily_usage_tracker is not None:
        _tavily_usage_tracker.reset()