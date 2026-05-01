# tefas-client for LLMs

This document explains how an LLM should use tefas-client safely and correctly when generating Python code, assistant responses, or automation scripts.

## 1. What tefas-client is

tefas-client is a synchronous, type-safe Python client for TEFAS fund data.

Primary use cases:
- Fetch fund prices (NAV) and key metrics
- Fetch historical data in a date range
- Optionally fetch portfolio allocation (asset breakdown)
- Query a single fund or all funds
- Get an instant fund snapshot (price, daily return, category rank, market share)
- Discover umbrella fund types and founder institutions
- Filter queries by fund type, umbrella type, or founder
- Request responses in Turkish or English

## 2. Install and import

Use Python 3.10+.

Install:
- pip install tefas-client
- uv pip install tefas-client
- poetry add tefas-client

Import:
- from tefas_client import Tefas
- Optional models: FundOverview, UmbrellaFundType, Founder
- Optional type alias: FundType  (Literal["YAT", "EMK", "BYF"])
- Optional exceptions: RateLimitError, EmptyResponseError, TefasError

## 3. Core mental model for LLMs

The main entrypoint is Tefas used as a context manager.

Pattern:
1. Open client with with Tefas() as tefas
2. Call one of the four methods:
   - tefas.fetch(...)          -> dict[str, Fund]        (time-series history)
   - tefas.fetch_overview(...) -> FundOverview           (instant snapshot)
   - tefas.fetch_fund_types()  -> list[UmbrellaFundType] (umbrella type codes)
   - tefas.fetch_founders()    -> list[Founder]          (founder codes)
3. For fetch(): read returned dictionary: dict[str, Fund]
4. Access fund history and latest record

Important:
- API is synchronous (no native async)
- Return type of fetch() is a mapping from fund code to Fund object
- For single-fund queries, still read from dictionary by code
- When fund_code is given without fund_type, type is auto-detected (YAT -> EMK -> BYF)
- lang="EN" switches all text fields (category names, titles) to English

## 4. Main API contract

Constructor:
- Tefas(timeout: float = 30.0, lang: str = "TR")
  - timeout: per-request HTTP timeout in seconds
  - lang: "TR" (Turkish, default) or "EN" (English) — affects text fields in all responses

Fetch method:
- tefas.fetch(
    fund_code: str | list[str] = "",
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    include_allocation: bool = False,
    fund_type: Literal["YAT", "EMK", "BYF"] | None = None,
    umbrella_type: int | None = None,
    founder_code: str | None = None,
  ) -> dict[str, Fund]

Parameter behavior:
- fund_code empty string means all funds
- fund_code can be a list of codes
- start_date defaults to end_date when omitted
- end_date defaults to today when omitted
- weekend or holiday dates are auto-adjusted to nearest Friday
- include_allocation=True adds allocation details
- fund_type: "YAT"=investment funds, "EMK"=pension(BES), "BYF"=ETFs
- fund_type=None + specific code: auto-detects by trying YAT, then EMK, then BYF
- umbrella_type: numeric code from fetch_fund_types(); filters to that umbrella category
- founder_code: string code from fetch_founders(); filters to that institution

Snapshot method:
- tefas.fetch_overview(fund_code: str) -> FundOverview
  - Returns instant current snapshot; not time-series
  - Raises EmptyResponseError if fund_code is invalid

Discovery methods:
- tefas.fetch_fund_types(fund_type: Literal["YAT", "EMK"] = "YAT", *, refresh: bool = False) -> list[UmbrellaFundType]
  - Returns list of umbrella categories with code (int) and name (str)
  - Use returned code values as umbrella_type= in fetch()
  - Results are cached per Tefas instance; pass refresh=True to force fresh fetch

- tefas.fetch_founders(fund_type: Literal["YAT", "EMK"] = "YAT", *, refresh: bool = False) -> list[Founder]
  - Returns list of founder institutions with code (str) and name (str)
  - Use returned code values as founder_code= in fetch()
  - Results are cached per Tefas instance; pass refresh=True to force fresh fetch

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

FundOverview (from fetch_overview):
- code: str
- title: str
- price: float | None
- daily_return: float | None
- shares: float | None
- market_cap: float | None
- category: str | None
- category_rank: int | None
- category_fund_count: int | None
- number_of_investors: int | None
- market_share: float | None

UmbrellaFundType (from fetch_fund_types):
- code: int
- name: str

Founder (from fetch_founders):
- code: str
- name: str
- fund_type: str | None

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

Instant snapshot of a single fund:

from tefas_client import Tefas

with Tefas() as tefas:
    ov = tefas.fetch_overview("IPB")
    print(ov.price, ov.daily_return, ov.category_rank, ov.market_share)

Discover fund types and founders, then filter:

from datetime import date
from tefas_client import Tefas

with Tefas() as tefas:
    types = tefas.fetch_fund_types()           # list[UmbrellaFundType]
    founders = tefas.fetch_founders()          # list[Founder]

    # Pick codes of interest, then pass to fetch()
    funds = tefas.fetch(
        fund_type="YAT",
        umbrella_type=104,
        founder_code="IPO",
        start_date=date(2024, 2, 1),
        end_date=date(2024, 2, 29),
    )

English language responses:

from tefas_client import Tefas

with Tefas(lang="EN") as tefas:
    ov = tefas.fetch_overview("IPB")
    print(ov.category)   # English category name
    types = tefas.fetch_fund_types()
    print(types[0].name) # English umbrella type name

ETF (BYF) fund query:

from datetime import date
from tefas_client import Tefas

with Tefas() as tefas:
    funds = tefas.fetch("AAK", fund_type="BYF", start_date=date(2024, 1, 1))

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
- When fund_code is given without fund_type, auto-detects by trying YAT -> EMK -> BYF in order

LLM guidance:
- Prefer one broader query over many small requests
- Reuse one context manager for multiple fetch calls (fetch, fetch_overview, etc.)
- Add retry wait logic when suggesting batch workflows
- For ETF funds, pass fund_type="BYF" explicitly or let auto-detect handle it
- Use fetch_fund_types() and fetch_founders() first when user wants to filter results
- Both methods cache results per instance; calling them multiple times is safe and cheap

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

If user wants ETF (exchange-traded fund) data:
- Explain that ETFs on TEFAS use fund_type="BYF"
- Or omit fund_type and let auto-detect find it (YAT -> EMK -> BYF)

If user wants to browse or filter available fund categories:
- Suggest fetch_fund_types() to list umbrella types
- Suggest fetch_founders() to list founder institutions
- Then pass returned codes to fetch() as umbrella_type= or founder_code=

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
- v2 API — production-ready and fully tested
- New in v2: lang parameter, fund_type/umbrella_type/founder_code on fetch(), fetch_overview(), fetch_fund_types(), fetch_founders(), FundOverview/UmbrellaFundType/Founder models
- fetch_fund_types() and fetch_founders() now cache results per instance with optional refresh=True parameter

If project docs change, update this file to stay aligned with README.md.
