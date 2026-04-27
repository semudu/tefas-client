"""Tests for Pydantic models: Fund, History, Allocation."""

from __future__ import annotations

from datetime import date

import pytest

from tefas_client._endpoints import AllocationRow, InfoRow
from tefas_client._models import Allocation, Fund, History


class TestInfoRow:
    def test_parse_valid_row(self):
        row = InfoRow.model_validate(
            {
                "fonKodu": "AAK",
                "fonUnvan": "Test Fund",
                "tarih": "2024-02-01",
                "fiyat": "23.45",
                "portfoyBuyukluk": "1234567",
                "tedPaySayisi": "5678900",
                "kisiSayisi": "100",
                "borsaBultenFiyat": None,
            }
        )
        assert row.fonKodu == "AAK"
        assert row.fiyat == pytest.approx(23.45)
        assert row.kisiSayisi == 100
        assert row.borsaBultenFiyat is None

    def test_empty_string_coerces_to_none(self):
        row = InfoRow.model_validate(
            {
                "fonKodu": "AAK",
                "fonUnvan": "Test Fund",
                "tarih": "2024-02-01",
                "fiyat": "",
                "portfoyBuyukluk": "",
                "tedPaySayisi": None,
                "kisiSayisi": "",
            }
        )
        assert row.fiyat is None
        assert row.portfoyBuyukluk is None
        assert row.tedPaySayisi is None
        assert row.kisiSayisi is None


class TestAllocationRow:
    def test_allocation_fields_extracts_numeric(self):
        row = AllocationRow.model_validate(
            {
                "fonKodu": "AAK",
                "tarih": "2024-02-01",
                "hs": "5.5",
                "yhs": "94.5",
                "d": "",
                "NOTES": "ignore",
            }
        )
        fields = row.allocation_fields()
        assert fields["hs"] == pytest.approx(5.5)
        assert fields["yhs"] == pytest.approx(94.5)
        assert "d" not in fields  # empty string skipped


class TestHistory:
    def test_from_row_without_allocation(self):
        row = InfoRow.model_validate(
            {
                "fonKodu": "AAK",
                "fonUnvan": "Test Fund",
                "tarih": "2024-02-01",
                "fiyat": 23.45,
            }
        )
        h = History.from_row(row)
        assert h.date == date(2024, 2, 1)
        assert h.price == pytest.approx(23.45)
        assert h.allocation is None

    def test_from_row_with_allocation(self):
        info_row = InfoRow.model_validate(
            {
                "fonKodu": "AAK",
                "fonUnvan": "Test Fund",
                "tarih": "2024-02-01",
                "fiyat": 23.45,
            }
        )
        alloc_row = AllocationRow.model_validate(
            {
                "fonKodu": "AAK",
                "tarih": "2024-02-01",
                "yhs": "98.5",
                "vm": "1.5",
            }
        )
        h = History.from_row(info_row, alloc_row)
        assert h.allocation is not None
        assert h.allocation.assets["yhs"] == pytest.approx(98.5)

    def test_date_parsing_iso_format(self):
        row = InfoRow.model_validate(
            {
                "fonKodu": "AAK",
                "fonUnvan": "Test Fund",
                "tarih": "2024-02-01",
                "fiyat": 10.0,
            }
        )
        h = History.from_row(row)
        assert h.date == date(2024, 2, 1)


class TestFund:
    def _make_history(self, date_str: str, price: float) -> History:
        row = InfoRow.model_validate(
            {"fonKodu": "AAK", "fonUnvan": "Test", "tarih": date_str, "fiyat": price}
        )
        return History.from_row(row)

    def test_latest_returns_most_recent(self):
        h1 = self._make_history("20240201", 10.0)
        h2 = self._make_history("20240202", 11.0)
        fund = Fund(code="AAK", title="Test Fund", history=[h1, h2])
        assert fund.latest() == h2

    def test_code_normalised_to_uppercase(self):
        h = self._make_history("20240201", 10.0)
        fund = Fund(code="aak", title="Test", history=[h])
        assert fund.code == "AAK"

    def test_empty_history_raises(self):
        with pytest.raises(Exception):
            Fund(code="AAK", title="Test", history=[])
