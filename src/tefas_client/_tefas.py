"""Public facade: ``Tefas`` class.

Typical usage::

    from tefas_client import Tefas

    # Standalone — each fetch opens its own connection
    tefas = Tefas()
    funds = tefas.fetch("AAK", start_date=date(2024, 1, 1), end_date=date(2024, 3, 31))
    print(funds["AAK"].latest().price)

    # Multiple codes at once
    funds = tefas.fetch(["AAK", "TLY"], start_date=date(2024, 1, 1))

    # BYF (Exchange Traded Fund) — type auto-detected
    funds = tefas.fetch("GOLD", start_date=date(2024, 1, 1))

    # Context manager — connection shared across calls
    with Tefas() as tefas:
        aak = tefas.fetch("AAK", start_date=date(2024, 2, 1))
        hhy = tefas.fetch("HHY", start_date=date(2024, 2, 1))

    # English language support
    with Tefas(lang="EN") as tefas:
        overview = tefas.fetch_overview("IPB")
        types = tefas.fetch_fund_types()

    # All pension funds explicitly
    funds = tefas.fetch(fund_type="EMK", start_date=date(2024, 2, 1))
"""

from __future__ import annotations

import logging
import warnings
from datetime import date
from typing import Literal

from ._client import TefasHttpClient
from ._endpoints import (
    ALLOCATION_URL,
    FUND_FOUNDERS_URL,
    FUND_OVERVIEW_URL,
    FUND_TYPES_URL,
    INFO_URL,
    AllocationRow,
    FounderRow,
    FundOverviewRow,
    FundTypeRow,
    InfoRow,
    RequestBody,
)
from ._models import Founder, Fund, FundOverview, History, UmbrellaFundType
from ._utils import chunk_date_range, dedupe, nearest_weekday

logger = logging.getLogger(__name__)

FundType = Literal["YAT", "EMK", "BYF"]

# Auto-detect probe order when fund_type is not specified
_AUTO_DETECT_ORDER: list[FundType] = ["YAT", "EMK", "BYF"]


class Tefas:
    """High-level client for the TEFAS fund data API.

    Can be used standalone or as a context manager for connection sharing::

        with Tefas() as tefas:
            aak = tefas.fetch("AAK", ...)
            hhy = tefas.fetch("HHY", ...)   # reuses same connection

    Parameters
    ----------
    timeout:
        Per-request timeout in seconds.
    lang:
        Response language. ``"TR"`` (default) or ``"EN"``. Applied to all
        requests made by this instance.
    """

    def __init__(self, timeout: float = 30.0, lang: str = "TR") -> None:
        self._timeout = timeout
        self._lang = lang.upper()
        self._client: TefasHttpClient | None = None
        self._fund_types_cache: dict[str, list[UmbrellaFundType]] = {}
        self._founders_cache: dict[str, list[Founder]] = {}

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> Tefas:
        self._client = TefasHttpClient(timeout=self._timeout)
        self._client.__enter__()
        return self

    def __exit__(self, *args: object) -> None:
        if self._client is not None:
            self._client.__exit__(*args)
            self._client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(
        self,
        fund_code: str | list[str] = "",
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        include_allocation: bool = False,
        fund_type: FundType | None = None,
        umbrella_type: int | None = None,
        founder_code: str | None = None,
    ) -> dict[str, Fund]:
        """Fetch fund history for *fund_code* (or all funds when empty).

        Large date ranges are transparently split into ≤28-day chunks to
        comply with the TEFAS API constraint.  Duplicate rows across chunks
        are deduplicated by ``(fund_code, date)``.

        Parameters
        ----------
        fund_code:
            TEFAS fund code (e.g. ``"AAK"``), a list of codes, or an empty
            string to return all funds.  When a specific code is given and
            *fund_type* is ``None``, the fund type is auto-detected: ``"YAT"``
            → ``"EMK"`` → ``"BYF"`` are tried in order.
        start_date:
            Inclusive start of the desired date range.  Defaults to
            *end_date* when omitted (single-day fetch).
        end_date:
            Inclusive end of the desired date range.  Defaults to today
            when omitted.
        include_allocation:
            When *True*, also fetch portfolio allocation data and attach it
            to each ``History`` entry.
        fund_type:
            ``"YAT"`` for investment funds, ``"EMK"`` for pension / BES funds,
            ``"BYF"`` for exchange-traded funds.  When ``None`` (default) and
            a specific code is given, the type is auto-detected.  When
            querying all funds (empty *fund_code*) the effective default is
            ``"YAT"``.
        umbrella_type:
            Numeric umbrella fund type code (e.g. ``104`` for equity funds).
            Obtain valid codes via :meth:`fetch_fund_types`.
        founder_code:
            Founder institution code (e.g. ``"AKP"``).  Obtain valid codes
            via :meth:`fetch_founders`.

        Returns
        -------
        dict[str, Fund]
            Mapping of fund code → ``Fund`` object.  Empty dict when no
            data is available.
        """
        end_raw = end_date or date.today()
        start_raw = start_date or end_raw

        end = nearest_weekday(end_raw)
        start = nearest_weekday(start_raw)

        if end_date is not None and end != end_raw:
            warnings.warn(
                f"end_date {end_raw} is a weekend; adjusted to {end}",
                UserWarning,
                stacklevel=2,
            )
        if start_date is not None and start != start_raw:
            warnings.warn(
                f"start_date {start_raw} is a weekend; adjusted to {start}",
                UserWarning,
                stacklevel=2,
            )

        codes: list[str] = [fund_code] if isinstance(fund_code, str) else list(fund_code)

        if self._client is not None:
            return self._fetch_all(
                self._client, codes, start, end, include_allocation,
                fund_type, umbrella_type, founder_code,
            )
        with TefasHttpClient(timeout=self._timeout) as client:
            return self._fetch_all(
                client, codes, start, end, include_allocation,
                fund_type, umbrella_type, founder_code,
            )

    def fetch_overview(self, fund_code: str) -> FundOverview:
        """Fetch an instant snapshot of a single fund (fonBilgiGetir).

        Returns the fund's latest price, daily return, category ranking,
        market share, and other summary metrics.  This is not a time-series;
        it reflects the current state at the time of the call.

        Parameters
        ----------
        fund_code:
            TEFAS fund code (e.g. ``"IPB"``).
        """
        body = RequestBody(fonKodu=fund_code.strip().upper(), dil=self._lang)
        if self._client is not None:
            rows = self._client.post(FUND_OVERVIEW_URL, body, raise_on_empty=True)
        else:
            with TefasHttpClient(timeout=self._timeout) as client:
                rows = client.post(FUND_OVERVIEW_URL, body, raise_on_empty=True)

        row = FundOverviewRow.model_validate(rows[0])
        return FundOverview.from_row(row)

    def fetch_fund_types(self, fund_type: FundType = "YAT", *, refresh: bool = False) -> list[UmbrellaFundType]:
        """List umbrella fund types (fonTurGetir).

        Results are cached for the lifetime of this instance.  Pass
        ``refresh=True`` to bypass the cache and fetch fresh data.

        Parameters
        ----------
        fund_type:
            ``"YAT"`` for investment funds (default) or ``"EMK"`` for pension.
        refresh:
            When *True*, ignore any cached result and fetch from the API.
        """
        if not refresh and fund_type in self._fund_types_cache:
            return self._fund_types_cache[fund_type]

        body = RequestBody(fonTipi=fund_type, dil=self._lang)
        if self._client is not None:
            rows = self._client.post(FUND_TYPES_URL, body)
        else:
            with TefasHttpClient(timeout=self._timeout) as client:
                rows = client.post(FUND_TYPES_URL, body)

        result: list[UmbrellaFundType] = []
        for raw in rows:
            try:
                result.append(UmbrellaFundType.from_row(FundTypeRow.model_validate(raw)))
            except Exception:
                logger.debug("Skipping malformed fund type row: %s", raw)
        self._fund_types_cache[fund_type] = result
        return result

    def fetch_founders(self, fund_type: FundType = "YAT", *, refresh: bool = False) -> list[Founder]:
        """List founder institutions (fonKurucuGetir).

        Results are cached for the lifetime of this instance.  Pass
        ``refresh=True`` to bypass the cache and fetch fresh data.

        Parameters
        ----------
        fund_type:
            ``"YAT"`` for investment funds (default) or ``"EMK"`` for pension.
        refresh:
            When *True*, ignore any cached result and fetch from the API.
        """
        if not refresh and fund_type in self._founders_cache:
            return self._founders_cache[fund_type]

        body = RequestBody(fonTipi=fund_type, dil=self._lang)
        if self._client is not None:
            rows = self._client.post(FUND_FOUNDERS_URL, body)
        else:
            with TefasHttpClient(timeout=self._timeout) as client:
                rows = client.post(FUND_FOUNDERS_URL, body)

        result: list[Founder] = []
        for raw in rows:
            try:
                result.append(Founder.from_row(FounderRow.model_validate(raw)))
            except Exception:
                logger.debug("Skipping malformed founder row: %s", raw)
        self._founders_cache[fund_type] = result
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_all(
        self,
        client: TefasHttpClient,
        codes: list[str],
        start: date,
        end: date,
        include_allocation: bool,
        fund_type: FundType | None,
        umbrella_type: int | None,
        founder_code: str | None,
    ) -> dict[str, Fund]:
        result: dict[str, Fund] = {}
        for code in codes:
            result.update(
                self._fetch_one(client, code, start, end, include_allocation, fund_type, umbrella_type, founder_code)
            )
        return result

    def _fetch_one(
        self,
        client: TefasHttpClient,
        fund_code: str,
        start: date,
        end: date,
        include_allocation: bool,
        fund_type: FundType | None,
        umbrella_type: int | None,
        founder_code: str | None,
    ) -> dict[str, Fund]:
        normalized = fund_code.strip().upper() or None

        if fund_type is not None:
            info_rows, alloc_rows = self._fetch_chunks(
                client, normalized, fund_type, start, end, include_allocation, umbrella_type, founder_code
            )
            return self._build_funds(info_rows, alloc_rows)

        # Auto-detect: try YAT → EMK → BYF (only when a specific code is given)
        for candidate in _AUTO_DETECT_ORDER:
            info_rows, alloc_rows = self._fetch_chunks(
                client, normalized, candidate, start, end, include_allocation, umbrella_type, founder_code
            )
            if info_rows:
                logger.debug("Auto-detected fund type %s for %s", candidate, normalized)
                return self._build_funds(info_rows, alloc_rows)
            if normalized is None:
                # No specific code → "all funds" query; don't cascade further
                break
            logger.debug("No %s results for %s; trying next type", candidate, normalized)

        return {}

    def _fetch_chunks(
        self,
        client: TefasHttpClient,
        fund_code: str | None,
        fund_type: FundType,
        start: date,
        end: date,
        include_allocation: bool,
        umbrella_type: int | None,
        founder_code: str | None,
    ) -> tuple[list[InfoRow], list[AllocationRow]]:
        info_rows: list[InfoRow] = []
        alloc_rows: list[AllocationRow] = []

        for chunk_start, chunk_end in chunk_date_range(start, end):
            body = RequestBody(
                fonTipi=fund_type,
                fonKodu=fund_code,
                basTarih=RequestBody.format_date(chunk_start),
                bitTarih=RequestBody.format_date(chunk_end),
                sfonTurKod=umbrella_type,
                kurucuKod=founder_code,
                dil=self._lang,
            )
            raw_info = client.post(INFO_URL, body)
            for row in raw_info:
                try:
                    info_rows.append(InfoRow.model_validate(row))
                except Exception:
                    logger.debug("Skipping malformed info row: %s", row)

            if include_allocation:
                raw_alloc = client.post(ALLOCATION_URL, body)
                for row in raw_alloc:
                    try:
                        alloc_rows.append(AllocationRow.model_validate(row))
                    except Exception:
                        logger.debug("Skipping malformed allocation row: %s", row)

        return (
            dedupe(info_rows, key=lambda r: (r.fonKodu, r.tarih)),
            dedupe(alloc_rows, key=lambda r: (r.fonKodu, r.tarih)),
        )

    def _build_funds(
        self,
        info_rows: list[InfoRow],
        alloc_rows: list[AllocationRow],
    ) -> dict[str, Fund]:
        alloc_map: dict[tuple[str, str], AllocationRow] = {
            (r.fonKodu, r.tarih): r for r in alloc_rows
        }
        grouped: dict[str, list[InfoRow]] = {}
        for row in info_rows:
            grouped.setdefault(row.fonKodu, []).append(row)

        return {
            code: Fund(
                code=code,
                title=rows[0].fonUnvan,
                history=[
                    History.from_row(r, alloc_map.get((r.fonKodu, r.tarih)))
                    for r in sorted(rows, key=lambda r: r.tarih)
                ],
            )
            for code, rows in grouped.items()
        }
