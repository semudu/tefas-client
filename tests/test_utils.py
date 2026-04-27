"""Tests for _utils.py: date chunking, nearest_weekday, dedupe."""

from __future__ import annotations

from datetime import date

import pytest

from tefas_client._utils import chunk_date_range, dedupe, nearest_weekday


class TestNearestWeekday:
    def test_weekday_unchanged(self):
        # 2024-01-15 is a Monday
        d = date(2024, 1, 15)
        assert nearest_weekday(d) == d

    def test_saturday_steps_to_friday(self):
        # 2024-01-20 is Saturday
        assert nearest_weekday(date(2024, 1, 20)) == date(2024, 1, 19)

    def test_sunday_steps_to_friday(self):
        # 2024-01-21 is Sunday
        assert nearest_weekday(date(2024, 1, 21)) == date(2024, 1, 19)

    def test_friday_unchanged(self):
        # 2024-01-19 is Friday
        d = date(2024, 1, 19)
        assert nearest_weekday(d) == d


class TestChunkDateRange:
    def test_single_day(self):
        chunks = chunk_date_range(date(2024, 1, 1), date(2024, 1, 1))
        assert chunks == [(date(2024, 1, 1), date(2024, 1, 1))]

    def test_exactly_28_days(self):
        start = date(2024, 1, 1)
        end = date(2024, 1, 28)
        chunks = chunk_date_range(start, end)
        assert len(chunks) == 1
        assert chunks[0] == (start, end)

    def test_29_days_splits_into_two(self):
        start = date(2024, 1, 1)
        end = date(2024, 1, 29)
        chunks = chunk_date_range(start, end)
        assert len(chunks) == 2
        assert chunks[0] == (date(2024, 1, 1), date(2024, 1, 28))
        assert chunks[1] == (date(2024, 1, 29), date(2024, 1, 29))

    def test_full_coverage(self):
        """All days in [start, end] must appear in exactly one chunk."""
        start = date(2024, 1, 1)
        end = date(2024, 4, 30)
        chunks = chunk_date_range(start, end)

        all_days: list[date] = []
        for cs, ce in chunks:
            assert cs <= ce
            from datetime import timedelta
            d = cs
            while d <= ce:
                all_days.append(d)
                d += timedelta(days=1)

        from datetime import timedelta
        expected: list[date] = []
        d = start
        while d <= end:
            expected.append(d)
            d += timedelta(days=1)

        assert all_days == expected

    def test_inverted_range_returns_empty(self):
        assert chunk_date_range(date(2024, 2, 1), date(2024, 1, 1)) == []

    def test_custom_chunk_size(self):
        start = date(2024, 1, 1)
        end = date(2024, 1, 10)
        chunks = chunk_date_range(start, end, days=3)
        # 10 days / 3 = ceil = 4 chunks
        assert len(chunks) == 4


class TestDedupe:
    def test_removes_duplicates(self):
        result = dedupe([1, 2, 2, 3, 1], key=lambda x: x)
        assert result == [1, 2, 3]

    def test_preserves_first_occurrence(self):
        items = [{"id": 1, "v": "a"}, {"id": 1, "v": "b"}, {"id": 2, "v": "c"}]
        result = dedupe(items, key=lambda x: x["id"])
        assert result == [{"id": 1, "v": "a"}, {"id": 2, "v": "c"}]

    def test_empty_input(self):
        assert dedupe([], key=lambda x: x) == []
