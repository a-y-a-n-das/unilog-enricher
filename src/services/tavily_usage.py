"""Tavily usage tracking service for research capacity estimation."""

import logging
from dataclasses import dataclass, field
from threading import Lock

from pipeline.llm.config import get_tavily_monthly_credits
from pipeline.research.search import SearchUsage

LOGGER = logging.getLogger(__name__)


@dataclass
class TavilyUsageSummary:
    """Summary of Tavily usage for capacity estimation."""

    credits_used_this_session: int = 0
    credits_remaining: int | None = None
    estimated_credits_per_row: int = 10
    monthly_credit_limit: int = 1000

    @property
    def estimated_rows_remaining(self) -> int | None:
        """Estimate rows remaining based on remaining credits.

        Returns None if remaining credits cannot be determined.
        """
        if self.credits_remaining is None:
            return None
        if self.estimated_credits_per_row <= 0:
            return None
        return max(0, self.credits_remaining // self.estimated_credits_per_row)

    @property
    def estimated_rows_from_limit(self) -> int:
        """Estimate rows remaining based on monthly limit minus session usage."""
        remaining_from_limit = max(0, self.monthly_credit_limit - self.credits_used_this_session)
        if self.estimated_credits_per_row <= 0:
            return 0
        return max(0, remaining_from_limit // self.estimated_credits_per_row)


class TavilyUsageTracker:
    """Thread-safe tracker for Tavily API usage across research rows."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._credits_used_this_session = 0
        self._credits_remaining: int | None = None
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

    def record_usage(self, usage: SearchUsage) -> None:
        """Record usage from a single Tavily search."""
        with self._lock:
            self._credits_used_this_session += usage.credits_used
            if usage.credits_remaining is not None:
                self._credits_remaining = usage.credits_remaining

    def get_summary(self) -> dict:
        """Get a summary of current usage for API response."""
        with self._lock:
            credits_used = self._credits_used_this_session
            credits_remaining = self._credits_remaining
            monthly_limit = self._monthly_limit
            estimated_per_row = self._estimated_credits_per_row

        # Determine best estimate for remaining credits
        estimated_remaining = None
        if credits_remaining is not None:
            estimated_remaining = credits_remaining
        elif monthly_limit > 0:
            estimated_remaining = max(0, monthly_limit - self._credits_used_this_session)

        estimated_rows = None
        if estimated_remaining is not None and estimated_per_row > 0:
            estimated_rows = max(0, estimated_remaining // estimated_per_row)

        return {
            "tavily": {
                "credits_used_this_session": credits_used,
                "credits_remaining": estimated_remaining,
                "estimated_credits_per_row": estimated_per_row,
                "estimated_rows_remaining": estimated_rows,
                "monthly_credit_limit": monthly_limit,
                "note": (
                    "Estimated values based on current session usage and configured "
                    "monthly limit. Actual remaining credits may differ. This is an "
                    "informational estimate only and does not block processing."
                ),
            }
    }

    def reset(self) -> None:
        """Reset the tracker (useful for testing)."""
        with self._lock:
            self._credits_used_this_session = 0
            self._credits_remaining = None


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