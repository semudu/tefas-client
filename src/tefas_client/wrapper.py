"""Public facade: ``Tefas`` class.

Typical usage::

    from tefas_client import Tefas

    # Standalone — each fetch opens its own connection
    tefas = Tefas()
    funds = tefas.fetch("AAK", start_date=date(2024, 1, 1), end_date=date(2024, 3, 31))
    print(funds["AAK"].latest().price)

    # Multiple codes at once
    funds = tefas.fetch(["AAK", "TLY"], start_date=date(2024, 1, 1))

    # Pension / BES fund — type auto-detected, no need to specify
    funds = tefas.fetch("HHY", start_date=date(2024, 1, 1))

    # Context manager — connection shared across calls
    with Tefas() as tefas:
        aak = tefas.fetch("AAK", start_date=date(2024, 2, 1))
        hhy = tefas.fetch("HHY", start_date=date(2024, 2, 1))

    # All pension funds explicitly
    funds = tefas.fetch(fund_type="EMK", start_date=date(2024, 2, 1))
"""

from __future__ import annotations

import logging
import warnings
from datetime import date
from typing import Literal

from ._client import TefasHttpClient
from ._endpoints import ALLOCATION_URL, INFO_URL, AllocationRow, InfoRow, RequestBody
from ._models import Fund, History
from ._utils import chunk_date_range, dedupe, nearest_weekday

logger = logging.getLogger(__name__)

FundType = Literal["YAT", "EMK"]


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
    """

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout
        self._client: TefasHttpClient | None = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "Tefas":
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
            is tried first and ``"EMK"`` is used as fallback.
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
            ``"YAT"`` for investment funds, ``"EMK"`` for pension / BES funds.
            When ``None`` (default) and a specific code is given, the type is
            auto-detected.  When querying all funds (empty *fund_code*) the
            effective default is ``"YAT"``.

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
            return self._fetch_all(self._client, codes, start, end, include_allocation, fund_type)
        with TefasHttpClient(timeout=self._timeout) as client:
            return self._fetch_all(client, codes, start, end, include_allocation, fund_type)

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
    ) -> dict[str, Fund]:
        result: dict[str, Fund] = {}
        for code in codes:
            result.update(self._fetch_one(client, code, start, end, include_allocation, fund_type))
        return result

    def _fetch_one(
        self,
        client: TefasHttpClient,
        fund_code: str,
        start: date,
        end: date,
        include_allocation: bool,
        fund_type: FundType | None,
    ) -> dict[str, Fund]:
        normalized = fund_code.strip().upper() or None

        if fund_type is not None:
            # Explicit type — use directly
            resolved: FundType = fund_type
        else:
            # No specific code → all YAT funds; specific code → try YAT first
            resolved = "YAT"

        info_rows, alloc_rows = self._fetch_chunks(
            client, normalized, resolved, start, end, include_allocation
        )

        # Auto-detect fallback: specific code, no explicit type, YAT returned nothing → try EMK
        if not info_rows and normalized is not None and fund_type is None:
            logger.debug("No YAT results for %s; retrying as EMK", normalized)
            info_rows, alloc_rows = self._fetch_chunks(
                client, normalized, "EMK", start, end, include_allocation
            )

        return self._build_funds(info_rows, alloc_rows)

    def _fetch_chunks(
        self,
        client: TefasHttpClient,
        fund_code: str | None,
        fund_type: FundType,
        start: date,
        end: date,
        include_allocation: bool,
    ) -> tuple[list[InfoRow], list[AllocationRow]]:
        info_rows: list[InfoRow] = []
        alloc_rows: list[AllocationRow] = []

        for chunk_start, chunk_end in chunk_date_range(start, end):
            body = RequestBody(
                fonTipi=fund_type,
                fonKodu=fund_code,
                basTarih=RequestBody.format_date(chunk_start),
                bitTarih=RequestBody.format_date(chunk_end),
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
