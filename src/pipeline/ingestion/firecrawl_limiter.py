import logging
import os
import time
from threading import Lock
from typing import Optional

import httpx

LOGGER = logging.getLogger(__name__)

# Hardcoded defaults (not configurable via env)
DEFAULT_TRIAL_RPM = 10
DEFAULT_TRIAL_CONCURRENT = 2
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_BACKOFF = 2.0

# Paid plan defaults (configurable via env)
DEFAULT_PAID_RPM = 1000
DEFAULT_PAID_CONCURRENT = 50

_trial_limiter: Optional["FirecrawlRateLimiter"] = None
_trial_limiter_lock = Lock()


class FirecrawlRateLimiter:
    """Thread-safe rate limiter for Firecrawl API shared across all workers."""

    def __init__(
        self,
        requests_per_minute: int = DEFAULT_TRIAL_RPM,
        max_concurrent: int = DEFAULT_TRIAL_CONCURRENT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_backoff: float = DEFAULT_BASE_BACKOFF,
    ) -> None:
        self.requests_per_minute = requests_per_minute
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries
        self.base_backoff = base_backoff

        self._request_times: list[float] = []
        self._active_requests = 0
        self._lock = Lock()

        self._min_interval = 60.0 / requests_per_minute if requests_per_minute > 0 else 0

    def acquire(self) -> None:
        """Acquire a permit, blocking until rate limit and concurrency allow."""
        while True:
            with self._lock:
                now = time.monotonic()

                self._request_times = [t for t in self._request_times if now - t < 60.0]

                if len(self._request_times) < self.requests_per_minute and self._active_requests < self.max_concurrent:
                    self._request_times.append(now)
                    self._active_requests += 1
                    return

                wait_time = 0.0
                if self._request_times:
                    oldest = self._request_times[0]
                    wait_time = max(wait_time, 60.0 - (now - oldest))
                if self._active_requests >= self.max_concurrent:
                    wait_time = max(wait_time, 0.5)

            if wait_time > 0:
                LOGGER.debug(
                    "Firecrawl rate limit reached, waiting %.2fs (active=%d, recent=%d/%d)",
                    wait_time,
                    self._active_requests,
                    len(self._request_times),
                    self.requests_per_minute,
                )
                time.sleep(min(wait_time, 1.0))

    def release(self) -> None:
        """Release a permit after request completes."""
        with self._lock:
            self._active_requests = max(0, self._active_requests - 1)

    def execute_with_retry(
        self,
        func,
        url: str,
        *args,
        **kwargs,
    ):
        """Execute function with rate limiting and 429 retry logic."""
        last_error = None

        for attempt in range(self.max_retries + 1):
            self.acquire()
            try:
                result = func(*args, **kwargs)

                if isinstance(result, httpx.Response) and result.status_code == 429:
                    raise FirecrawlRateLimitError(
                        "Rate limit exceeded",
                        response=result,
                    )

                return result

            except FirecrawlRateLimitError as e:
                last_error = e
                self.release()

                retry_after = self._get_retry_after(e.response)
                if retry_after is None:
                    retry_after = self.base_backoff * (2 ** attempt)

                LOGGER.warning(
                    "Firecrawl 429 for %s (attempt %d/%d), retrying in %.1fs",
                    url,
                    attempt + 1,
                    self.max_retries + 1,
                    retry_after,
                )
                time.sleep(retry_after)

            except Exception as e:
                last_error = e
                self.release()
                raise

            finally:
                if self._active_requests > 0:
                    with self._lock:
                        if self._active_requests > 0:
                            self._active_requests -= 1

        raise FirecrawlRateLimitError(
            f"Firecrawl rate limit exceeded after {self.max_retries + 1} attempts for {url}",
            response=last_error.response if isinstance(last_error, FirecrawlRateLimitError) else None,
        ) from last_error

    def _get_retry_after(self, response: Optional[httpx.Response]) -> Optional[float]:
        if response is None:
            return None
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass
        return None


class FirecrawlRateLimitError(Exception):
    def __init__(self, message: str, response: Optional[httpx.Response] = None):
        super().__init__(message)
        self.response = response


def get_firecrawl_limiter() -> FirecrawlRateLimiter:
    """Get or create the global Firecrawl rate limiter (singleton)."""
    global _trial_limiter

    with _trial_limiter_lock:
        if _trial_limiter is None:
            trial_mode = os.getenv("FIRECRAWL_TRIAL", "").lower() in ("true", "1", "yes")

            if trial_mode:
                rpm = int(os.getenv("FIRECRAWL_TRIAL_RPM", str(DEFAULT_TRIAL_RPM)))
                concurrent = DEFAULT_TRIAL_CONCURRENT
                max_retries = DEFAULT_MAX_RETRIES
                base_backoff = DEFAULT_BASE_BACKOFF

                LOGGER.info(
                    "Firecrawl trial mode enabled: %d RPM, %d concurrent, %d max retries",
                    rpm,
                    concurrent,
                    max_retries,
                )
            else:
                rpm = int(os.getenv("FIRECRAWL_RPM", str(DEFAULT_PAID_RPM)))
                concurrent = int(os.getenv("FIRECRAWL_CONCURRENT", str(DEFAULT_PAID_CONCURRENT)))
                max_retries = DEFAULT_MAX_RETRIES
                base_backoff = DEFAULT_BASE_BACKOFF

                LOGGER.info(
                    "Firecrawl paid mode: %d RPM, %d concurrent, %d max retries",
                    rpm,
                    concurrent,
                    max_retries,
                )

            _trial_limiter = FirecrawlRateLimiter(
                requests_per_minute=rpm,
                max_concurrent=concurrent,
                max_retries=max_retries,
                base_backoff=base_backoff,
            )

        return _trial_limiter


def reset_firecrawl_limiter() -> None:
    """Reset the global limiter (for testing)."""
    global _trial_limiter
    with _trial_limiter_lock:
        _trial_limiter = None