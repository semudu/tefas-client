"""Tests for fetch_overview, fetch_fund_types, fetch_founders, lang parameter."""

from __future__ import annotations

import json
from pathlib import Path

from pytest_httpx import HTTPXMock

from tefas_client import Founder, FundOverview, Tefas, UmbrellaFundType
from tefas_client._endpoints import FUND_FOUNDERS_URL, FUND_OVERVIEW_URL, FUND_TYPES_URL, INFO_URL

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class TestFetchOverview:
    def test_returns_fund_overview(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=FUND_OVERVIEW_URL, method="POST", json=_load("fund_overview.json"))
        tefas = Tefas()
        overview = tefas.fetch_overview("IPB")
        assert isinstance(overview, FundOverview)
        assert overview.code == "IPB"
        assert overview.title == "İş Portföy Para Piyasası Fonu"
        assert overview.price == 1.234567
        assert overview.daily_return == 0.05
        assert overview.category == "Para Piyasası Fonu"
        assert overview.category_rank == 3
        assert overview.category_fund_count == 45
        assert overview.market_share == 2.15

    def test_fund_code_normalised_to_upper(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=FUND_OVERVIEW_URL, method="POST", json=_load("fund_overview.json"))
        tefas = Tefas()
        overview = tefas.fetch_overview("ipb")
        assert overview.code == "IPB"

    def test_context_manager_reuses_connection(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=FUND_OVERVIEW_URL, method="POST", json=_load("fund_overview.json"))
        httpx_mock.add_response(url=FUND_OVERVIEW_URL, method="POST", json=_load("fund_overview.json"))
        with Tefas() as tefas:
            ov1 = tefas.fetch_overview("IPB")
            ov2 = tefas.fetch_overview("IPB")
        assert ov1.code == ov2.code == "IPB"
        assert len(httpx_mock.get_requests()) == 2


class TestFetchFundTypes:
    def test_returns_umbrella_fund_types(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=FUND_TYPES_URL, method="POST", json=_load("fund_types.json"))
        tefas = Tefas()
        types = tefas.fetch_fund_types()
        assert len(types) == 3
        assert all(isinstance(t, UmbrellaFundType) for t in types)

    def test_type_fields(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=FUND_TYPES_URL, method="POST", json=_load("fund_types.json"))
        tefas = Tefas()
        types = tefas.fetch_fund_types()
        equity = next(t for t in types if t.code == 104)
        assert equity.name == "Hisse Senedi Şemsiye Fonu"

    def test_empty_response_returns_empty_list(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=FUND_TYPES_URL, method="POST", json={"errorCode": 0, "resultList": []})
        tefas = Tefas()
        assert tefas.fetch_fund_types() == []


class TestFetchFounders:
    def test_returns_founder_list(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=FUND_FOUNDERS_URL, method="POST", json=_load("founders.json"))
        tefas = Tefas()
        founders = tefas.fetch_founders()
        assert len(founders) == 3
        assert all(isinstance(f, Founder) for f in founders)

    def test_founder_fields(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=FUND_FOUNDERS_URL, method="POST", json=_load("founders.json"))
        tefas = Tefas()
        founders = tefas.fetch_founders()
        ak = next(f for f in founders if f.code == "AKP")
        assert "AK PORTFÖY" in ak.name
        assert ak.fund_type == "F"

    def test_code_normalised_to_upper(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=FUND_FOUNDERS_URL, method="POST", json=_load("founders.json"))
        tefas = Tefas()
        founders = tefas.fetch_founders()
        assert all(f.code == f.code.upper() for f in founders)


class TestLangParameter:
    def test_lang_sent_in_request(self, httpx_mock: HTTPXMock):
        """Requests made with lang='EN' must include dil='EN' in the body."""
        httpx_mock.add_response(url=FUND_TYPES_URL, method="POST", json=_load("fund_types.json"))
        tefas = Tefas(lang="EN")
        tefas.fetch_fund_types()
        request = httpx_mock.get_requests()[0]
        import json as _json
        body = _json.loads(request.content)
        assert body["dil"] == "EN"

    def test_default_lang_is_tr(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=FUND_TYPES_URL, method="POST", json=_load("fund_types.json"))
        tefas = Tefas()
        tefas.fetch_fund_types()
        request = httpx_mock.get_requests()[0]
        import json as _json
        body = _json.loads(request.content)
        assert body["dil"] == "TR"


class TestFetchFilters:
    def test_umbrella_type_sent_in_request(self, httpx_mock: HTTPXMock):
        from datetime import date
        httpx_mock.add_response(url=INFO_URL, method="POST", json=_load("fund_info.json"))
        tefas = Tefas()
        tefas.fetch("AAK", start_date=date(2024, 2, 1), end_date=date(2024, 2, 2), fund_type="YAT", umbrella_type=104)
        request = httpx_mock.get_requests()[0]
        import json as _json
        body = _json.loads(request.content)
        assert body["sfonTurKod"] == 104

    def test_founder_code_sent_in_request(self, httpx_mock: HTTPXMock):
        from datetime import date
        httpx_mock.add_response(url=INFO_URL, method="POST", json=_load("fund_info.json"))
        tefas = Tefas()
        tefas.fetch("AAK", start_date=date(2024, 2, 1), end_date=date(2024, 2, 2), fund_type="YAT", founder_code="AKP")
        request = httpx_mock.get_requests()[0]
        import json as _json
        body = _json.loads(request.content)
        assert body["kurucuKod"] == "AKP"
