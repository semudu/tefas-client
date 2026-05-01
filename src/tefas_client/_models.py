"""Domain models: Fund, History, Allocation.

These are the objects returned to library users.  They are intentionally
decoupled from the wire-format field names defined in _endpoints.py.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, field_validator, model_validator

from ._endpoints import AllocationRow, FounderRow, FundOverviewRow, FundTypeRow, InfoRow

# ---------------------------------------------------------------------------
# Asset-code → human-readable name mapping
# Updated for the post-2024 TEFAS allocation schema.
# ---------------------------------------------------------------------------
_ASSET_NAMES: dict[str, str] = {
    "hs": "Hisse Senedi",
    "yhs": "Yabanci Hisse Senedi",
    "dt": "Devlet Ic Borclanma Araclari",
    "kks": "Kira Sertifikasi (Devlet)",
    "osks": "Kira Sertifikasi (Ozel Sektor)",
    "ost": "Ozel Sektor Tahvili",
    "hb": "Hazine Bonosu",
    "fb": "Finansman Bonosu",
    "eut": "Dis Borclanma Araclari (Eurobond)",
    "r": "Repo",
    "tr": "Ters Repo",
    "vm": "Vadeli Mevduat (TL)",
    "vmtl": "Vadeli Mevduat (TL)",
    "vmd": "Vadeli Mevduat (Doviz)",
    "vmau": "Vadeli Mevduat (Altin)",
    "kh": "Katilim Hesabi",
    "khtl": "Katilim Hesabi (TL)",
    "khd": "Katilim Hesabi (Doviz)",
    "khau": "Katilim Hesabi (Altin)",
    "km": "Kiymetli Madenler",
    "kmbyf": "Kiymetli Maden BYF",
    "kmkba": "Kiymetli Maden KBA",
    "kmkks": "Kiymetli Maden Kira Sertifikasi",
    "kba": "Kamu Dis Borclanma Araclari",
    "yba": "Yabanci Borclanma Araclari",
    "ybkb": "Yabanci Kamu Borc. Araclari",
    "ybosb": "Yabanci Ozel Sektor Borc. Araclari",
    "ybyf": "Yabanci BYF",
    "byf": "Borsa Yatirim Fonu",
    "gykb": "Girisim Yatirim Kurulusu Payi",
    "gsykb": "Girisim Sermayesi Yatirim Kuruluu Payi",
    "gyy": "Girisim Sermayesi Yatirim Fonu",
    "gsyy": "Girişim Sermayesi Yatirim Yonetim Fonu",
    "gas": "Gayrimenkul Sertifikasi",
    "vdm": "Varliga Dayali Menkul Kiymet",
    "db": "Doviz Odemenli Tahvil",
    "dot": "Doviz Odemenli Tahvil",
    "t": "Turev Araclar",
    "vint": "Vadeli Islem ve Opsiyon (Net)",
    "tpp": "Takasbank Para Piyasasi",
    "yyf": "Yatirim Yonetim Fonu",
    "kibd": "Kira Sertifikasi / Ici Borclanma",
    "kksd": "Kira Sertifikasi (Doviz)",
    "kkstl": "Kira Sertifikasi (TL)",
    "kksyd": "Kira Sertifikasi (Yabanci Doviz)",
    "bb": "Banka Bonosu",
    "oksyd": "Ozel Kira Sertifikasi (Yabanci Doviz)",
    "osdb": "Ozel Sektor Dis Borclanma Araclari",
    "ymk": "Yabanci Menkul Kiymet",
    "fkb": "Fon Katilma Belgesi",
    "bpp": "Borsada Para Piyasasi",
    "btaa": "Borclanma Araclari (TL Altin)",
    "btas": "Borclanma Araclari (TL Altin Sertifikasi)",
    "d": "Diger",
}


def _parse_tefas_date(raw: str) -> date:
    """Parse a TEFAS date string to a ``datetime.date``.

    Handles both ``YYYYMMDD`` and ``YYYY-MM-DD`` formats.
    """
    raw = raw.strip()
    if len(raw) == 8 and raw.isdigit():
        return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
    # ISO-like: YYYY-MM-DD or YYYY-MM-DDT...
    return date.fromisoformat(raw[:10])


# ---------------------------------------------------------------------------
# Allocation
# ---------------------------------------------------------------------------


class Allocation(BaseModel):
    """Portföy dağılımı: bir fona ait tek günlük varlık dağılımı."""

    date: date
    assets: dict[str, float]  # {asset_code: percentage}
    asset_names: dict[str, str]  # {asset_code: human-readable name}

    model_config = {"frozen": True}

    @classmethod
    def from_row(cls, row: AllocationRow) -> Allocation:
        raw_assets = row.allocation_fields()
        names = {code: _ASSET_NAMES.get(code, code) for code in raw_assets}
        return cls(
            date=_parse_tefas_date(row.tarih),
            assets=raw_assets,
            asset_names=names,
        )


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


class History(BaseModel):
    """Bir fona ait tek günlük tarihsel veri noktası."""

    date: date
    price: float | None = None
    market_cap: float | None = None
    number_of_shares: float | None = None
    number_of_investors: int | None = None
    exchange_bulletin_price: float | None = None
    allocation: Allocation | None = None

    model_config = {"frozen": True}

    @classmethod
    def from_row(cls, row: InfoRow, alloc: AllocationRow | None = None) -> History:
        return cls(
            date=_parse_tefas_date(row.tarih),
            price=row.fiyat,
            market_cap=row.portfoyBuyukluk,
            number_of_shares=row.tedPaySayisi,
            number_of_investors=row.kisiSayisi,
            exchange_bulletin_price=row.borsaBultenFiyat,
            allocation=Allocation.from_row(alloc) if alloc is not None else None,
        )


# ---------------------------------------------------------------------------
# Fund
# ---------------------------------------------------------------------------


class Fund(BaseModel):
    """Bir yatırım fonuna ait meta veri ve tarihsel veriler."""

    code: str
    title: str
    history: list[History]

    model_config = {"frozen": True}

    @field_validator("code")
    @classmethod
    def normalise_code(cls, v: str) -> str:
        return v.strip().upper()

    @model_validator(mode="before")
    @classmethod
    def check_history_not_empty(cls, data: Any) -> Any:
        history = data.get("history") if isinstance(data, dict) else None
        if history is not None and len(history) == 0:
            raise ValueError("Fund must have at least one History entry")
        return data

    def latest(self) -> History:
        """Return the most recent History entry by date."""
        return max(self.history, key=lambda h: h.date)


# ---------------------------------------------------------------------------
# FundOverview
# ---------------------------------------------------------------------------


class FundOverview(BaseModel):
    """Anlık fon özet bilgisi — fonBilgiGetir snapshot'ından türetilir.

    History modelinden farklı olarak tarih içermez; bu veri API'den çekildiği
    andaki son durumun anlık görüntüsüdür (zaman serisi değil).
    """

    code: str
    title: str
    price: float | None = None
    daily_return: float | None = None
    shares: int | None = None
    market_cap: float | None = None
    category: str | None = None
    category_rank: int | None = None
    category_fund_count: int | None = None
    number_of_investors: int | None = None
    market_share: float | None = None

    model_config = {"frozen": True}

    @classmethod
    def from_row(cls, row: FundOverviewRow) -> FundOverview:
        return cls(
            code=row.fonKodu.strip().upper(),
            title=row.fonUnvan,
            price=row.sonFiyat,
            daily_return=row.gunlukGetiri,
            shares=row.payAdet,
            market_cap=row.portBuyukluk,
            category=row.fonKategori,
            category_rank=row.kategoriDerece,
            category_fund_count=row.kategoriFonSay,
            number_of_investors=row.yatirimciSayi,
            market_share=row.pazarPayi,
        )


# ---------------------------------------------------------------------------
# UmbrellaFundType
# ---------------------------------------------------------------------------


class UmbrellaFundType(BaseModel):
    """Şemsiye fon türü — fonTurGetir'den türetilir."""

    code: int
    name: str

    model_config = {"frozen": True}

    @classmethod
    def from_row(cls, row: FundTypeRow) -> UmbrellaFundType:
        return cls(code=row.sfonTuru, name=row.sfonTurAciklama)


# ---------------------------------------------------------------------------
# Founder
# ---------------------------------------------------------------------------


class Founder(BaseModel):
    """Fon kurucu kurum — fonKurucuGetir'den türetilir."""

    code: str
    name: str
    fund_type: str | None = None  # "F" (yatırım fonu) veya "M" (emeklilik)

    model_config = {"frozen": True}

    @classmethod
    def from_row(cls, row: FounderRow) -> Founder:
        return cls(
            code=row.kurucuKodu.strip().upper(),
            name=row.kurucuUnvan,
            fund_type=row.fonTipi,
        )
