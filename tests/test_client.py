"""Tests for TefasHttpClient: retry, rate-limit, empty responses."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from pytest_httpx import HTTPXMock

from tefas_client._client import TefasHttpClient
from tefas_client._endpoints import INFO_URL, RequestBody
from tefas_client.exceptions import EmptyResponseError, RateLimitError, TefasError

FIXTURES = Path(__file__).parent / "fixtures"


def _body() -> RequestBody:
    return RequestBody(fonTipi="YAT", basTarih="20240201", bitTarih="20240228")


def _info_payload() -> dict:
    return json.loads((FIXTURES / "fund_info.json").read_text())


def _empty_payload() -> dict:
    return json.loads((FIXTURES / "empty_response.json").read_text())


class TestTefasHttpClientSuccess:
    def test_returns_result_list(self, httpx_mock: HTTPXMock):
        payload = _info_payload()
        httpx_mock.add_response(url=INFO_URL, method="POST", json=payload)
        with TefasHttpClient() as client:
            rows = client.post(INFO_URL, _body())
        assert len(rows) == 2
        assert rows[0]["fonKodu"] == "AAK"

    def test_empty_result_list_returns_empty(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=INFO_URL, method="POST", json=_empty_payload())
        with TefasHttpClient() as client:
            rows = client.post(INFO_URL, _body())
        assert rows == []

    def test_empty_result_list_raises_when_flagged(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=INFO_URL, method="POST", json=_empty_payload())
        with TefasHttpClient() as client, pytest.raises(EmptyResponseError):
            client.post(INFO_URL, _body(), raise_on_empty=True)


class TestTefasHttpClientErrors:
    def test_non_200_raises_tefas_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url=INFO_URL, method="POST", status_code=503)
        with TefasHttpClient() as client, pytest.raises(TefasError):
            client.post(INFO_URL, _body())

    def test_rate_limit_429_raises_rate_limit_error(self, httpx_mock: HTTPXMock):
        # Return 429 for every retry attempt
        for _ in range(3):
            httpx_mock.add_response(
                url=INFO_URL,
                method="POST",
                status_code=429,
                headers={"Retry-After": "1"},
            )
        with TefasHttpClient() as client, pytest.raises(RateLimitError) as exc_info:
            client.post(INFO_URL, _body())
        assert exc_info.value.retry_after == pytest.approx(1.0)

    def test_network_error_raises_tefas_error(self, httpx_mock: HTTPXMock):
        for _ in range(3):
            httpx_mock.add_exception(
                httpx.NetworkError("connection refused"), url=INFO_URL, method="POST"
            )
        with TefasHttpClient() as client, pytest.raises(TefasError):
            client.post(INFO_URL, _body())

    def test_invalid_json_raises_tefas_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url=INFO_URL, method="POST", status_code=200, text="not json"
        )
        with TefasHttpClient() as client, pytest.raises(TefasError):
            client.post(INFO_URL, _body())


class TestTefasHttpClientContextManager:
    def test_must_use_as_context_manager(self):
        client = TefasHttpClient()
        with pytest.raises(RuntimeError):
            client.post(INFO_URL, _body())
