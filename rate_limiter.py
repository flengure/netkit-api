"""
Multi-level rate limiting for API requests.

Supports three levels:
- Global: Limit total requests across all clients
- Per-IP: Limit requests from individual IP addresses
- Per-API-key: Limit requests from individual API keys
"""

import time
import logging
from collections import defaultdict
from threading import Lock
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Multi-level rate limiter with sliding window.

    All limits are per-minute by default.
    """

    def __init__(
        self,
        global_limit: int = 100,
        per_ip_limit: int = 20,
        per_key_limit: int = 50,
        window_seconds: int = 60
    ):
        """
        Initialize rate limiter

        Args:
            global_limit: Maximum requests per minute globally
            per_ip_limit: Maximum requests per minute per IP
            per_key_limit: Maximum requests per minute per API key
            window_seconds: Time window for rate limiting (default: 60s)
        """
        self.global_limit = global_limit
        self.per_ip_limit = per_ip_limit
        self.per_key_limit = per_key_limit
        self.window_seconds = window_seconds

        # Request tracking
        self.global_requests: list[float] = []
        self.ip_requests: dict[str, list[float]] = defaultdict(list)
        self.key_requests: dict[str, list[float]] = defaultdict(list)

        self.lock = Lock()

        logger.info(
            f"Rate limiter initialized: global={global_limit}, "
            f"per_ip={per_ip_limit}, per_key={per_key_limit}, "
            f"window={window_seconds}s"
        )

    def _cleanup_old_requests(self, request_list: list[float]) -> list[float]:
        """
        Remove requests older than the window

        Args:
            request_list: List of request timestamps

        Returns:
            Filtered list with only recent requests
        """
        now = time.time()
        cutoff = now - self.window_seconds
        return [ts for ts in request_list if ts > cutoff]

    def check_limit(
        self,
        ip: str,
        api_key: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Check if request is allowed under all rate limits

        Args:
            ip: Client IP address
            api_key: Optional API key

        Returns:
            (allowed: bool, reason: str)
                - (True, "") if request is allowed
                - (False, "reason") if request is rate limited
        """
        with self.lock:
            now = time.time()

            # Clean up old requests
            self.global_requests = self._cleanup_old_requests(self.global_requests)
            self.ip_requests[ip] = self._cleanup_old_requests(self.ip_requests[ip])

            if api_key:
                self.key_requests[api_key] = self._cleanup_old_requests(
                    self.key_requests[api_key]
                )

            # Check global limit
            if len(self.global_requests) >= self.global_limit:
                logger.warning(
                    f"Global rate limit exceeded: {len(self.global_requests)}/{self.global_limit}"
                )
                return False, "Global rate limit exceeded. Try again later."

            # Check per-IP limit
            if len(self.ip_requests[ip]) >= self.per_ip_limit:
                logger.warning(
                    f"IP rate limit exceeded for {ip}: "
                    f"{len(self.ip_requests[ip])}/{self.per_ip_limit}"
                )
                return False, f"Rate limit exceeded for your IP address. Try again later."

            # Check per-API-key limit
            if api_key:
                if len(self.key_requests[api_key]) >= self.per_key_limit:
                    logger.warning(
                        f"API key rate limit exceeded: "
                        f"{len(self.key_requests[api_key])}/{self.per_key_limit}"
                    )
                    return False, "Rate limit exceeded for your API key. Try again later."

            # All checks passed - record request
            self.global_requests.append(now)
            self.ip_requests[ip].append(now)
            if api_key:
                self.key_requests[api_key].append(now)

            return True, ""

    def get_stats(self) -> dict:
        """
        Get current rate limiter statistics

        Returns:
            Dictionary with current request counts
        """
        with self.lock:
            # Clean up before reporting
            self.global_requests = self._cleanup_old_requests(self.global_requests)

            return {
                "global": {
                    "current": len(self.global_requests),
                    "limit": self.global_limit,
                    "window_seconds": self.window_seconds
                },
                "per_ip": {
                    "limit": self.per_ip_limit,
                    "tracked_ips": len(self.ip_requests)
                },
                "per_key": {
                    "limit": self.per_key_limit,
                    "tracked_keys": len(self.key_requests)
                }
            }

    def reset(self):
        """Reset all rate limit counters (for testing)"""
        with self.lock:
            self.global_requests.clear()
            self.ip_requests.clear()
            self.key_requests.clear()
            logger.info("Rate limiter reset")
