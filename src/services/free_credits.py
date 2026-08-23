"""Application-level free credits tracker for row processing tracking (informational only, no persistence)."""

import logging
import os
from dataclasses import dataclass
from threading import Lock

LOGGER = logging.getLogger(__name__)

DEFAULT_FREE_CREDITS = 100


@dataclass
class FreeCreditsSummary:
    """Summary of free credits for UI display."""

    remaining_credits: int
    initial_credits: int
    credits_used_this_session: int

    @property
    def note(self) -> str:
        return (
            "This is a free trial with limited row processing. "
            "Each attempted row uses 1 credit. "
            "Upgrade for unlimited processing."
        )


class FreeCreditsTracker:
    """Thread-safe tracker for application free credits (informational only, no persistence).

    Resets to FREE_CREDITS env value on every startup.
    """

    def __init__(self, initial_credits: int | None = None) -> None:
        self._lock = Lock()
        self._initial_credits = initial_credits or self._load_initial_credits()
        self._remaining_credits = self._initial_credits
        self._credits_used_this_session = 0

    def _load_initial_credits(self) -> int:
        """Load initial credits from environment variable."""
        value = os.getenv("FREE_CREDITS")
        if value is not None:
            try:
                credits = int(value)
                if credits < 0:
                    LOGGER.warning("FREE_CREDITS cannot be negative: %s, using default %d", value, DEFAULT_FREE_CREDITS)
                    return DEFAULT_FREE_CREDITS
                return credits
            except ValueError:
                LOGGER.warning("Invalid FREE_CREDITS value: %s, using default %d", value, DEFAULT_FREE_CREDITS)
        return DEFAULT_FREE_CREDITS

    def configure(self, initial_credits: int | None = None) -> None:
        """Configure the tracker with initial credits."""
        with self._lock:
            if initial_credits is not None:
                self._initial_credits = initial_credits
                self._remaining_credits = initial_credits

    def can_process_row(self) -> bool:
        """Always returns True - tracking is informational only, doesn't block processing."""
        return True

    def consume_credit(self) -> bool:
        """Consume one credit for an attempted row (informational only).

        Always returns True - credits can go negative for tracking purposes.
        """
        with self._lock:
            self._remaining_credits -= 1
            self._credits_used_this_session += 1
            return True

    def get_remaining(self) -> int:
        """Get remaining credits (can be negative)."""
        with self._lock:
            return self._remaining_credits

    def get_summary(self) -> FreeCreditsSummary:
        """Get summary for API response."""
        with self._lock:
            return FreeCreditsSummary(
                remaining_credits=self._remaining_credits,
                initial_credits=self._initial_credits,
                credits_used_this_session=self._credits_used_this_session,
            )

    def reset(self) -> None:
        """Reset the tracker (useful for testing)."""
        with self._lock:
            self._remaining_credits = self._initial_credits
            self._credits_used_this_session = 0


# Module-level singleton
_free_credits_tracker: FreeCreditsTracker | None = None


def get_free_credits_tracker() -> FreeCreditsTracker:
    """Get the global free credits tracker instance."""
    global _free_credits_tracker
    if _free_credits_tracker is None:
        _free_credits_tracker = FreeCreditsTracker()
    return _free_credits_tracker


def reset_free_credits_tracker() -> None:
    """Reset the global tracker (useful for testing)."""
    global _free_credits_tracker
    if _free_credits_tracker is not None:
        _free_credits_tracker.reset()
    _free_credits_tracker = None