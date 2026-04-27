# tefas-wrapper v2

Python client for fetching fund data from [TEFAS](https://www.tefas.gov.tr) (Türkiye Elektronik Fon Alım Satım Platformu).

> **v2 is a complete rewrite.** The API is not backwards-compatible with v1.

## Requirements

- Python >= 3.10
- Dependencies: `httpx`, `pydantic` (both installed automatically)

## Installation

```bash
pip install tefas-wrapper
```

## Quick start

```python
from datetime import date
from tefas_client import Tefas

tefas = Tefas()

# Single fund, single day
funds = tefas.fetch("AAK", start_date=date(2024, 2, 1), end_date=date(2024, 2, 1))
fund = funds["AAK"]
print(fund.title)          # "Ak Portfoy Amerikan Dolar Yabanci BYF"
print(fund.latest().price) # 23.456789

# Date range – automatically chunked into <=28-day requests
funds = tefas.fetch("AAK", start_date=date(2024, 1, 1), end_date=date(2024, 3, 31))
for h in funds["AAK"].history:
    print(h.date, h.price)

# Portfolio allocation breakdown
funds = tefas.fetch(
    "AAK",
    start_date=date(2024, 2, 1),
    end_date=date(2024, 2, 28),
    include_allocation=True,
)
h = funds["AAK"].latest()
if h.allocation:
    for code, pct in h.allocation.assets.items():
        name = h.allocation.asset_names[code]
        print(f"  {name}: {pct:.2f}%")

# All funds
all_funds = Tefas().fetch(start_date=date(2024, 2, 1), end_date=date(2024, 2, 1))
```

## API reference

### `Tefas(timeout=30.0)`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `timeout` | `float` | `30.0` | Per-request HTTP timeout in seconds |

### `Tefas.fetch(fund_code="", *, start_date=None, end_date=None, include_allocation=False)`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `fund_code` | `str` | `""` | TEFAS code (e.g. `"AAK"`). Empty = all funds |
| `start_date` | `date` | `end_date` | Inclusive range start |
| `end_date` | `date` | today | Inclusive range end |
| `include_allocation` | `bool` | `False` | Also fetch portfolio allocation data |

Returns `dict[str, Fund]` — mapping of fund code to `Fund`.

### `Fund`

| Field | Type | Description |
|-------|------|-------------|
| `code` | `str` | TEFAS fund code |
| `title` | `str` | Full fund name |
| `history` | `list[History]` | Chronological data points |

`fund.latest()` returns the most recent `History` entry.

### `History`

| Field | Type | Description |
|-------|------|-------------|
| `date` | `date` | Trading date |
| `price` | `float or None` | Fund unit price (NAV) |
| `market_cap` | `float or None` | Portfolio size (TRY) |
| `number_of_shares` | `float or None` | Total circulating shares |
| `number_of_investors` | `int or None` | Investor count |
| `exchange_bulletin_price` | `float or None` | Exchange bulletin price (BYF only) |
| `allocation` | `Allocation or None` | Portfolio allocation (if requested) |

### `Allocation`

| Field | Type | Description |
|-------|------|-------------|
| `date` | `date` | Allocation date |
| `assets` | `dict[str, float]` | `{asset_code: percentage}` |
| `asset_names` | `dict[str, str]` | `{asset_code: human-readable name}` |

## Exceptions

| Exception | When |
|-----------|------|
| `TefasError` | Base class for all library errors |
| `RateLimitError` | API returned HTTP 429 after retries; has `retry_after` float attribute |
| `EmptyResponseError` | API returned success but no rows |

## Known constraints

| Constraint | Detail |
|-----------|--------|
| **Rate limit** | TEFAS allows ~6 requests/minute. The client retries with exponential back-off but raises `RateLimitError` after 3 failed attempts. |
| **28-day window** | Each TEFAS request supports at most ~28 calendar days. `fetch()` splits larger ranges automatically. |
| **Weekend/holiday dates** | TEFAS has no data for weekends. Date boundaries are automatically rolled back to the nearest Friday. |
| **WAF restrictions** | The TEFAS WAF may block requests from datacenter IP ranges. Use a residential/VPN connection if you encounter persistent 403/503 errors. |
| **No async** | v2 is synchronous-only. Async support is planned for a future release. |

## Development

```bash
git clone https://github.com/semudu/tefas-wrapper
cd tefas-wrapper
make install   # pip install -e ".[dev]"
make test      # pytest
make lint      # ruff + mypy
make format    # ruff format + ruff --fix
make build     # hatch build
```

## License

[MIT](LICENSE)
