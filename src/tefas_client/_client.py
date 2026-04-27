"""Low-level HTTP client for the TEFAS JSON API.

Wraps ``httpx.Client`` with:
- Browser-like headers required by the TEFAS WAF
- Automatic retry with exponential back-off
- ``RateLimitError`` on HTTP 429
- ``EmptyResponseError`` when ``resultList`` is null or empty (optional guard)
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from ._endpoints import REFERER_URL, BASE_URL, RequestBody
from .exceptions import EmptyResponseError, RateLimitError, TefasError

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0
_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0  # seconds; delay = base ** attempt

_DEFAULT_HEADERS: dict[str, str] = {
    "Origin": BASE_URL,
    "Referer": REFERER_URL,
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Content-Type": "application/json",
}


class TefasHttpClient:
    """Stateful HTTP client for TEFAS API POST requests.

    Intended to be used as a context manager::

        with TefasHttpClient() as client:
            rows = client.post(INFO_URL, body)
    """

    def __init__(self, timeout: float = _DEFAULT_TIMEOUT) -> None:
        self._timeout = timeout
        self._client: httpx.Client | None = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "TefasHttpClient":
        self._client = httpx.Client(
            headers=_DEFAULT_HEADERS,
            timeout=self._timeout,
            follow_redirects=True,
        )
        return self

    def __exit__(self, *_: object) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def post(
        self,
        url: str,
        body: RequestBody,
        *,
        raise_on_empty: bool = False,
    ) -> list[dict[str, Any]]:
        """POST *body* to *url* and return the ``resultList``.

        Parameters
        ----------
        url:
            Full endpoint URL (use constants from ``_endpoints``).
        body:
            Validated ``RequestBody`` instance.
        raise_on_empty:
            If *True*, raise ``EmptyResponseError`` when ``resultList`` is
            empty instead of returning ``[]``.
        """
        if self._client is None:
            raise RuntimeError("TefasHttpClient must be used as a context manager")

        payload = body.model_dump()
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                response = self._client.post(url, json=payload)
            except httpx.TimeoutException as exc:
                logger.warning("TEFAS request timed out (attempt %d/%d)", attempt + 1, _MAX_RETRIES)
                last_exc = exc
                self._sleep_backoff(attempt)
                continue
            except httpx.RequestError as exc:
                logger.warning(
                    "TEFAS network error %s (attempt %d/%d)", exc, attempt + 1, _MAX_RETRIES
                )
                last_exc = exc
                self._sleep_backoff(attempt)
                continue

            if response.status_code == 429:
                retry_after = self._parse_retry_after(response)
                if attempt < _MAX_RETRIES - 1:
                    logger.warning(
                        "Rate limited by TEFAS, waiting %.0fs (attempt %d/%d)",
                        retry_after or _BACKOFF_BASE ** (attempt + 1),
                        attempt + 1,
                        _MAX_RETRIES,
                    )
                    time.sleep(retry_after or _BACKOFF_BASE ** (attempt + 1))
                    continue
                raise RateLimitError(retry_after)

            if response.status_code != 200:
                raise TefasError(
                    f"TEFAS API returned HTTP {response.status_code}: {response.text[:200]}"
                )

            try:
                data: dict[str, Any] = response.json()
            except Exception as exc:
                raise TefasError(f"Invalid JSON from TEFAS API: {exc}") from exc

            result_list: list[dict[str, Any]] | None = data.get("resultList")
            if result_list is None:
                result_list = []

            if raise_on_empty and len(result_list) == 0:
                raise EmptyResponseError(
                    f"TEFAS returned no data rows for request to {url}"
                )

            return result_list

        # All retries exhausted
        if last_exc is not None:
            raise TefasError(
                f"TEFAS request failed after {_MAX_RETRIES} attempts"
            ) from last_exc
        raise TefasError(f"TEFAS request failed after {_MAX_RETRIES} attempts")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_retry_after(response: httpx.Response) -> float | None:
        header = response.headers.get("Retry-After")
        if header is None:
            return None
        try:
            return float(header)
        except ValueError:
            return None

    @staticmethod
    def _sleep_backoff(attempt: int) -> None:
        delay = _BACKOFF_BASE ** (attempt + 1)
        logger.debug("Back-off %.1fs", delay)
        time.sleep(delay)
