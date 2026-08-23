"""Application-level free credits tracker for row processing tracking (informational only)."""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

LOGGER = logging.getLogger(__name__)

DEFAULT_FREE_CREDITS = 100
CREDITS_FILE = Path("/app/data/free_credits.json")


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
    """Thread-safe tracker for application free credits (informational only, does not block processing)."""

    def __init__(self, initial_credits: int | None = None) -> None:
        self._lock = Lock()
        self._initial_credits = initial_credits or self._load_initial_credits()
        self._remaining_credits = self._load_remaining_credits()
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

    def _load_remaining_credits(self) -> int:
        """Load remaining credits from persistent storage."""
        if CREDITS_FILE.exists():
            try:
                with CREDITS_FILE.open("r") as f:
                    data = json.load(f)
                    remaining = data.get("remaining_credits")
                    if isinstance(remaining, int):
                        return max(0, remaining)
            except (json.JSONDecodeError, OSError) as e:
                LOGGER.warning("Failed to load credits from %s: %s", CREDITS_FILE, e)
        return self._initial_credits

    def _save_remaining_credits(self) -> None:
        """Save remaining credits to persistent storage."""
        try:
            CREDITS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with CREDITS_FILE.open("w") as f:
                json.dump({"remaining_credits": self._remaining_credits}, f)
        except OSError as e:
            LOGGER.error("Failed to save credits to %s: %s", CREDITS_FILE, e)

    def configure(self, initial_credits: int | None = None) -> None:
        """Configure the tracker with initial credits."""
        with self._lock:
            if initial_credits is not None:
                self._initial_credits = initial_credits
                if self._remaining_credits > initial_credits:
                    self._remaining_credits = initial_credits
                    self._save_remaining_credits()

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
            self._save_remaining_credits()
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
            self._save_remaining_credits()


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