"""TEFAS API endpoint constants and Pydantic request/response DTOs.

The new TEFAS infrastructure (post-2024 rewrite) exposes JSON endpoints under
https://www.tefas.gov.tr/api/funds/.  These DTOs describe the wire format so
that the rest of the package never has to know raw field names.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# URL constants
# ---------------------------------------------------------------------------

BASE_URL = "https://www.tefas.gov.tr"
REFERER_URL = f"{BASE_URL}/tr/fon-verileri"
INFO_URL = f"{BASE_URL}/api/funds/fonGnlBlgSiraliGetir"
ALLOCATION_URL = f"{BASE_URL}/api/funds/dagilimSiraliGetirT"

# ---------------------------------------------------------------------------
# Request body
# ---------------------------------------------------------------------------


class RequestBody(BaseModel):
    """Wire-format body sent to TEFAS JSON endpoints."""

    fonTipi: str = ""
    fonKodu: str | None = None
    aramaMetni: str | None = None
    fonTurKod: str | None = None
    fonGrubu: str | None = None
    sfonTurKod: str | None = None
    basTarih: str  # YYYYMMDD
    bitTarih: str  # YYYYMMDD
    basSira: int = 1
    bitSira: int = 9999
    fonTurAciklama: str | None = None
    dil: str = "TR"
    kurucuKod: str | None = None
    sira: str | None = None
    yon: str | None = None

    @staticmethod
    def format_date(d: date) -> str:
        return d.strftime("%Y%m%d")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Response DTOs
# ---------------------------------------------------------------------------


class InfoRow(BaseModel):
    """One row from /api/funds/fonGnlBlgSiraliGetir resultList."""

    fonKodu: str
    fonUnvan: str
    tarih: str  # "YYYY-MM-DD" ISO format
    fiyat: float | None = None
    portfoyBuyukluk: float | None = None
    tedPaySayisi: float | None = None
    kisiSayisi: int | None = None
    borsaBultenFiyat: float | None = None
    rn: int | None = None

    model_config = {"extra": "allow", "populate_by_name": True}

    @field_validator("fiyat", "portfoyBuyukluk", "tedPaySayisi", "borsaBultenFiyat", mode="before")
    @classmethod
    def coerce_float(cls, v: Any) -> float | None:
        if v is None or v == "":
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    @field_validator("kisiSayisi", mode="before")
    @classmethod
    def coerce_int(cls, v: Any) -> int | None:
        if v is None or v == "":
            return None
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return None


class AllocationRow(BaseModel):
    """One row from /api/funds/dagilimSiraliGetirT resultList.

    Allocation fields are percentage values (0–100) keyed by asset code.
    The full set of codes is captured via ``model_config extra='allow'``.
    Non-allocation fields (fonUnvan, bilFiyat) are declared explicitly so
    they are excluded from the extra dict and never appear in allocation_fields().
    """

    fonKodu: str
    tarih: str
    fonUnvan: str | None = None
    bilFiyat: str | None = None  # internal TEFAS timestamp string, not a percentage

    model_config = {"extra": "allow", "populate_by_name": True}

    def allocation_fields(self) -> dict[str, float]:
        """Return all extra fields as {code: percentage}, skipping non-numeric."""
        result: dict[str, float] = {}
        for key, value in self.model_extra.items():  # type: ignore[union-attr]
            if value is None or value == "":
                continue
            try:
                result[key] = float(value)
            except (TypeError, ValueError):
                continue
        return result
