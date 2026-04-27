"""Custom exceptions for tefas_client."""

from __future__ import annotations


class TefasError(Exception):
    """Base exception for all tefas_client errors."""


class RateLimitError(TefasError):
    """Raised when the TEFAS API returns HTTP 429 or signals rate limiting."""

    def __init__(self, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        msg = "TEFAS rate limit exceeded"
        if retry_after is not None:
            msg += f"; retry after {retry_after:.0f}s"
        super().__init__(msg)


class EmptyResponseError(TefasError):
    """Raised when the API returns a success status but no data rows."""
