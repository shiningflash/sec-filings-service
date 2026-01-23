"""SEC HTTP client with retry, rate limiting, and proper headers.

This module provides the single HTTP gateway for all SEC EDGAR requests.
No other modules should implement HTTP directly.
"""

import time
from typing import Any

import requests
from requests.exceptions import ConnectionError, ReadTimeout, Timeout
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.core.logging import get_logger
from src.core.settings import DEFAULT_MAX_PER_SECOND, DEFAULT_RETRIES, DEFAULT_TIMEOUT
from src.core.utils import simple_rate_limiter

logger = get_logger(__name__)


class RetryableHttpError(Exception):
    """Exception for HTTP errors that should trigger a retry."""

    def __init__(self, status_code: int, retry_after: float | None = None):
        self.status_code = status_code
        self.retry_after = retry_after
        super().__init__(f"HTTP {status_code}")


class NonRetryableHttpError(Exception):
    """Exception for HTTP errors that should NOT be retried (4xx except 429)."""

    def __init__(self, status_code: int, message: str = ""):
        self.status_code = status_code
        self.message = message
        super().__init__(f"HTTP {status_code}: {message}")


def _log_retry(retry_state: RetryCallState) -> None:
    """Log retry attempts for debugging."""
    if retry_state.outcome and retry_state.outcome.failed:
        exc = retry_state.outcome.exception()
        logger.warning(
            "Retry attempt %d failed: %s. Retrying...",
            retry_state.attempt_number,
            exc,
        )


class SecHttpClient:
    """HTTP client for SEC EDGAR API with rate limiting and retries.

    All SEC requests should go through this client to ensure:
    - Proper User-Agent header is set
    - Rate limiting is enforced
    - Retries with exponential backoff for transient errors
    - Retry-After header is respected

    Attributes:
        user_agent: Descriptive User-Agent string with contact email.
        max_per_second: Maximum requests per second (default: 2).
        retries: Number of retry attempts for transient errors (default: 3).
        timeout: Tuple of (connect_timeout, read_timeout) in seconds.
    """

    def __init__(
        self,
        user_agent: str,
        max_per_second: float = DEFAULT_MAX_PER_SECOND,
        retries: int = DEFAULT_RETRIES,
        timeout: tuple[float, float] = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the SEC HTTP client.

        Args:
            user_agent: Descriptive User-Agent string (must include email).
            max_per_second: Maximum requests per second.
            retries: Number of retry attempts for transient errors.
            timeout: Tuple of (connect_timeout, read_timeout) in seconds.
        """
        self.user_agent = user_agent
        self.max_per_second = max_per_second
        self.retries = retries
        self.timeout = timeout

        # Create session for connection reuse
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept-Encoding": "gzip, deflate",
            }
        )

        # Rate limiter
        self._rate_limit = simple_rate_limiter(max_per_second)

        logger.debug(
            "SecHttpClient initialized: rate=%.1f/s, retries=%d, timeout=%s",
            max_per_second,
            retries,
            timeout,
        )

    def _make_request(self, url: str) -> requests.Response:
        """Make an HTTP GET request with rate limiting.

        Args:
            url: The URL to request.

        Returns:
            The response object.

        Raises:
            RetryableHttpError: For 429 or 5xx errors (will be retried).
            NonRetryableHttpError: For 4xx errors except 429 (will not retry).
            ConnectionError: For connection issues (will be retried by tenacity).
            Timeout: For timeout issues (will be retried by tenacity).
        """
        # Apply rate limiting
        self._rate_limit()

        logger.debug("GET %s", url)

        response = self._session.get(url, timeout=self.timeout)

        logger.debug(
            "Response: %d %s (%.2f KB)",
            response.status_code,
            response.reason,
            len(response.content) / 1024,
        )

        # Handle response status
        if response.ok:
            return response

        # Parse Retry-After header if present
        retry_after: float | None = None
        if "Retry-After" in response.headers:
            try:
                retry_after = float(response.headers["Retry-After"])
                logger.info("Retry-After header: %.1f seconds", retry_after)
            except ValueError:
                pass

        # 429 Too Many Requests - retryable
        if response.status_code == 429:
            if retry_after:
                logger.warning("Rate limited (429). Sleeping %.1fs...", retry_after)
                time.sleep(retry_after)
            raise RetryableHttpError(429, retry_after)

        # 5xx Server Errors - retryable
        if 500 <= response.status_code < 600:
            raise RetryableHttpError(response.status_code, retry_after)

        # 4xx Client Errors (except 429) - not retryable
        if 400 <= response.status_code < 500:
            raise NonRetryableHttpError(
                response.status_code, response.text[:200] if response.text else ""
            )

        # Other unexpected status codes
        response.raise_for_status()
        return response  # Should not reach here

    def _get_with_retry(self, url: str) -> requests.Response:
        """Make request with tenacity retry logic.

        Retries on:
        - RetryableHttpError (429, 5xx)
        - ConnectionError
        - Timeout/ReadTimeout
        """

        @retry(
            stop=stop_after_attempt(self.retries + 1),  # +1 because first try counts
            wait=wait_exponential(multiplier=1, min=1, max=30),
            retry=retry_if_exception_type(
                (RetryableHttpError, ConnectionError, Timeout, ReadTimeout)
            ),
            before_sleep=_log_retry,
            reraise=True,
        )
        def _do_request() -> requests.Response:
            return self._make_request(url)

        return _do_request()

    def get_json(self, url: str) -> dict[str, Any]:
        """Fetch JSON data from a URL.

        Args:
            url: The URL to fetch JSON from.

        Returns:
            Parsed JSON as a dictionary.

        Raises:
            NonRetryableHttpError: For 4xx errors (except 429).
            RetryableHttpError: If all retries exhausted for transient errors.
            requests.JSONDecodeError: If response is not valid JSON.
        """
        logger.info("Fetching JSON: %s", url)
        response = self._get_with_retry(url)
        return response.json()

    def get_text(self, url: str) -> str:
        """Fetch text content from a URL.

        Args:
            url: The URL to fetch text from.

        Returns:
            Response body as text string.

        Raises:
            NonRetryableHttpError: For 4xx errors (except 429).
            RetryableHttpError: If all retries exhausted for transient errors.
        """
        logger.info("Fetching text: %s", url)
        response = self._get_with_retry(url)
        return response.text

    def get_bytes(self, url: str) -> bytes:
        """Fetch binary content from a URL.

        Args:
            url: The URL to fetch bytes from.

        Returns:
            Response body as bytes.

        Raises:
            NonRetryableHttpError: For 4xx errors (except 429).
            RetryableHttpError: If all retries exhausted for transient errors.
        """
        logger.info("Fetching bytes: %s", url)
        response = self._get_with_retry(url)
        return response.content

    def close(self) -> None:
        """Close the underlying session."""
        self._session.close()
        logger.debug("SecHttpClient session closed")

    def __enter__(self) -> "SecHttpClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - close session."""
        self.close()
