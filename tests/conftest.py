"""Shared pytest fixtures and helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import tefas_client._client as _tefas_client_module

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch time.sleep inside _client.py to a no-op so retry back-offs and jitter are instant."""
    monkeypatch.setattr(
        _tefas_client_module, "time", type("_T", (), {"sleep": staticmethod(lambda s: None)})()
    )


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture()
def fund_info_payload() -> dict:
    return load_fixture("fund_info.json")


@pytest.fixture()
def allocation_payload() -> dict:
    return load_fixture("allocation.json")


@pytest.fixture()
def empty_payload() -> dict:
    return load_fixture("empty_response.json")
