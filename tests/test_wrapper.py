"""End-to-end tests for Tefas.fetch() with mocked HTTP."""

from __future__ import annotations

import json
import warnings
from contextlib import suppress
from datetime import date
from pathlib import Path

from pytest_httpx import HTTPXMock

from tefas_client import FundType, Tefas
from tefas_client._endpoints import ALLOCATION_URL, INFO_URL

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class TestTefasFetch:
    def test_fetch_returns_fund_dict(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=INFO_URL, method="POST", json=_load("fund_info.json"))
        tefas = Tefas()
        result = tefas.fetch("AAK", start_date=date(2024, 2, 1), end_date=date(2024, 2, 2))
        assert "AAK" in result
        fund = result["AAK"]
        assert fund.code == "AAK"
        assert len(fund.history) == 2

    def test_fetch_with_allocation(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=INFO_URL, method="POST", json=_load("fund_info.json"))
        httpx_mock.add_response(url=ALLOCATION_URL, method="POST", json=_load("allocation.json"))
        tefas = Tefas()
        result = tefas.fetch(
            "AAK",
            start_date=date(2024, 2, 1),
            end_date=date(2024, 2, 2),
            include_allocation=True,
        )
        fund = result["AAK"]
        h = fund.history[0]
        assert h.allocation is not None
        assert "yhs" in h.allocation.assets

    def test_fetch_empty_returns_empty_dict(self, httpx_mock: HTTPXMock):
        # Auto-detect: tries YAT first (empty), then EMK fallback (also empty)
        httpx_mock.add_response(url=INFO_URL, method="POST", json=_load("empty_response.json"))
        httpx_mock.add_response(url=INFO_URL, method="POST", json=_load("empty_response.json"))
        tefas = Tefas()
        result = tefas.fetch("NONEXIST", start_date=date(2024, 2, 1), end_date=date(2024, 2, 1))
        assert result == {}

    def test_fetch_chunks_large_range(self, httpx_mock: HTTPXMock):
        """A 90-day range should produce 4 HTTP calls (ceil(90/28)=4 chunks)."""
        for _ in range(4):
            httpx_mock.add_response(url=INFO_URL, method="POST", json=_load("empty_response.json"))
        tefas = Tefas()
        # Use explicit fund_type to test chunking in isolation (no auto-detect fallback)
        tefas.fetch("AAK", start_date=date(2024, 1, 1), end_date=date(2024, 3, 31), fund_type="YAT")
        assert len(httpx_mock.get_requests()) == 4

    def test_fetch_default_end_date_is_today(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=INFO_URL, method="POST", json=_load("empty_response.json"))
        tefas = Tefas()
        # Should not raise; uses today as end_date (explicit fund_type avoids auto-detect)
        tefas.fetch("AAK", fund_type="YAT")

    def test_latest_returns_most_recent(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=INFO_URL, method="POST", json=_load("fund_info.json"))
        tefas = Tefas()
        result = tefas.fetch("AAK", start_date=date(2024, 2, 1), end_date=date(2024, 2, 2))
        fund = result["AAK"]
        latest = fund.latest()
        assert latest.date == date(2024, 2, 2)

    def test_auto_detect_emk_fund(self, httpx_mock: HTTPXMock):
        """When YAT returns nothing for a code, auto-detect falls back to EMK."""
        # First call: YAT → empty
        httpx_mock.add_response(url=INFO_URL, method="POST", json=_load("empty_response.json"))
        # Second call: EMK → data
        httpx_mock.add_response(url=INFO_URL, method="POST", json=_load("fund_info.json"))
        tefas = Tefas()
        result = tefas.fetch("HHY", start_date=date(2024, 2, 1), end_date=date(2024, 2, 2))
        assert len(result) > 0
        assert len(httpx_mock.get_requests()) == 2

    def test_fetch_multiple_codes(self, httpx_mock: HTTPXMock):
        """A list of fund codes triggers one request per code."""
        httpx_mock.add_response(url=INFO_URL, method="POST", json=_load("fund_info.json"))
        httpx_mock.add_response(url=INFO_URL, method="POST", json=_load("fund_info.json"))
        tefas = Tefas()
        result = tefas.fetch(
            ["AAK", "TLY"],
            start_date=date(2024, 2, 1),
            end_date=date(2024, 2, 2),
            fund_type="YAT",
        )
        assert "AAK" in result
        assert len(httpx_mock.get_requests()) == 2

    def test_context_manager_reuses_connection(self, httpx_mock: HTTPXMock):
        """Context manager usage works and allows multiple fetches."""
        httpx_mock.add_response(url=INFO_URL, method="POST", json=_load("fund_info.json"))
        httpx_mock.add_response(url=INFO_URL, method="POST", json=_load("empty_response.json"))
        with Tefas() as tefas:
            r1 = tefas.fetch("AAK", start_date=date(2024, 2, 1), end_date=date(2024, 2, 2))
            # fund_type explicit → no auto-detect fallback, exactly 1 request
            r2 = tefas.fetch("NONE", start_date=date(2024, 2, 1), end_date=date(2024, 2, 1), fund_type="YAT")
        assert "AAK" in r1
        assert r2 == {}

    def test_fund_type_exported(self):
        """FundType is importable from the public namespace."""
        assert FundType is not None

    def test_weekend_start_date_warns(self):
        """Passing a weekend start_date emits a UserWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            tefas = Tefas()
            # 2024-02-03 is a Saturday
            with suppress(Exception):
                tefas.fetch("AAK", start_date=date(2024, 2, 3), end_date=date(2024, 2, 3), fund_type="YAT")
        assert any(issubclass(warning.category, UserWarning) for warning in w)
