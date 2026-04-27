"""Pure-stdlib utility helpers: date chunking, weekday snapping, deduplication."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date, timedelta
from typing import TypeVar

T = TypeVar("T")

_CHUNK_DAYS = 28


def nearest_weekday(d: date) -> date:
    """Return *d* unchanged if it is a weekday, otherwise step back to Friday.

    TEFAS does not publish data on weekends.  Stepping backward (not forward)
    avoids accidentally requesting data from the future.
    """
    while d.weekday() > 4:  # 5=Sat, 6=Sun
        d -= timedelta(days=1)
    return d


def chunk_date_range(
    start: date,
    end: date,
    days: int = _CHUNK_DAYS,
) -> list[tuple[date, date]]:
    """Split [start, end] into contiguous chunks of at most *days* calendar days.

    Both *start* and *end* are inclusive.  The final chunk may be shorter.
    Returns an empty list when *start* > *end*.
    """
    if start > end:
        return []
    chunks: list[tuple[date, date]] = []
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(chunk_start + timedelta(days=days - 1), end)
        chunks.append((chunk_start, chunk_end))
        chunk_start = chunk_end + timedelta(days=1)
    return chunks


def dedupe(
    items: Iterable[T],
    key: Callable[[T], object],
) -> list[T]:
    """Return *items* with duplicates removed, preserving first occurrence order."""
    seen: set[object] = set()
    result: list[T] = []
    for item in items:
        k = key(item)
        if k not in seen:
            seen.add(k)
            result.append(item)
    return result
