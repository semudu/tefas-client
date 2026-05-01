# tefas-client for LLMs

This document explains how an LLM should use tefas-client safely and correctly when generating Python code, assistant responses, or automation scripts.

## 1. What tefas-client is

tefas-client is a synchronous, type-safe Python client for TEFAS fund data.

Primary use cases:
- Fetch fund prices (NAV) and key metrics
- Fetch historical data in a date range
- Optionally fetch portfolio allocation (asset breakdown)
- Query a single fund or all funds

## 2. Install and import

Use Python 3.10+.

Install:
- pip install tefas-client
- uv pip install tefas-client
- poetry add tefas-client

Import:
- from tefas_client import Tefas
- Optional exceptions: RateLimitError, EmptyResponseError, TefasError

## 3. Core mental model for LLMs

The main entrypoint is Tefas used as a context manager.

Pattern:
1. Open client with with Tefas() as tefas
2. Call tefas.fetch(...)
3. Read returned dictionary: dict[str, Fund]
4. Access fund history and latest record

Important:
- API is synchronous (no native async)
- Return type is a mapping from fund code to Fund object
- For single-fund queries, still read from dictionary by code

## 4. Main API contract

Constructor:
- Tefas(timeout: float = 30.0)

Fetch method:
- tefas.fetch(
    fund_code: str = "",
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    include_allocation: bool = False
  ) -> dict[str, Fund]

Parameter behavior:
- fund_code empty string means all funds
- start_date defaults to end_date when omitted
- end_date defaults to today when omitted
- weekend or holiday dates are auto-adjusted to nearest Friday
- include_allocation=True adds allocation details

## 5. Data objects returned

Fund:
- code: str
- title: str
- history: list[History] (oldest to newest)
- latest(): History (most recent)

History:
- date: date
- price: float | None
- market_cap: float | None
- number_of_shares: float | None
- number_of_investors: int | None
- exchange_bulletin_price: float | None
- allocation: Allocation | None

Allocation:
- date: date
- assets: dict[str, float]  # ISIN -> percentage
- asset_names: dict[str, str]  # ISIN -> security name

## 6. Canonical code snippets LLM should generate

Single fund, single day:

from datetime import date
from tefas_client import Tefas

with Tefas() as tefas:
    funds = tefas.fetch("AAK", start_date=date(2024, 2, 1), end_date=date(2024, 2, 1))
    latest = funds["AAK"].latest()
    print(latest.price)

Date range with allocation:

from datetime import date
from tefas_client import Tefas

with Tefas() as tefas:
    funds = tefas.fetch(
        "AAK",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 3, 31),
        include_allocation=True,
    )
    for row in funds["AAK"].history:
        if row.allocation:
            for isin, pct in row.allocation.assets.items():
                name = row.allocation.asset_names.get(isin, isin)
                print(isin, name, pct)

All funds for a day:

from datetime import date
from tefas_client import Tefas

with Tefas() as tefas:
    all_funds = tefas.fetch(start_date=date.today(), end_date=date.today())
    print(len(all_funds))

## 7. Error handling policy for LLM outputs

Preferred exception order:
1. EmptyResponseError for no rows
2. RateLimitError for throttling
3. TefasError as generic fallback

Example:

from datetime import date
from tefas_client import Tefas, EmptyResponseError, RateLimitError, TefasError

try:
    with Tefas() as tefas:
        funds = tefas.fetch("AAK", start_date=date(2024, 1, 1), end_date=date(2024, 1, 10))
except EmptyResponseError:
    print("No data in selected range")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds")
except TefasError as e:
    print(f"TEFAS error: {e}")

## 8. Constraints LLM must respect

Operational constraints from TEFAS:
- Rate limit is about 6 requests/minute
- Single query window is about 28 days
- No weekend/holiday trading data
- Datacenter IPs may receive 403/503 due to WAF

Library behavior:
- Handles larger date spans via chunking
- Retries with backoff for transient issues
- Raises RateLimitError after retry limits

LLM guidance:
- Prefer one broader query over many small requests
- Reuse one context manager for multiple fetch calls
- Add retry wait logic when suggesting batch workflows

## 9. Performance guidance for generated solutions

Generate this pattern:
- One with Tefas() block around all related queries
- Fetch all funds once, then filter in Python when possible
- Keep date ranges as small as business need allows

Avoid this pattern:
- Opening/closing Tefas for each fund
- Querying many codes separately for the same date

## 10. When LLM should propose alternatives

If user needs async:
- State that tefas-client is synchronous
- Suggest asyncio.to_thread(...) wrapper

If user gets 403/503 repeatedly:
- Explain likely WAF/IP block
- Suggest residential network or appropriate proxy strategy

If user gets EmptyResponseError:
- Suggest widening date range
- Suggest checking fund availability on selected date

## 11. LLM response template

When answering end users about tefas-client, prefer this structure:
1. Minimal install line
2. One short working code sample
3. One error-handling sample (if relevant)
4. One sentence on limits (rate limit / date window)

Keep examples production-safe:
- Include imports
- Include explicit dates in examples
- Include safe exception handling for networked usage

## 12. Version note

Based on README claims:
- Stable v1 API
- Production-ready and fully tested

If project docs change, update this file to stay aligned with README.md.
