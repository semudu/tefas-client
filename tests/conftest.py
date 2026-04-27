"""Shared pytest fixtures and helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


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
