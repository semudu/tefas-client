# tefas-client

[![PyPI - Version](https://img.shields.io/pypi/v/tefas-client.svg)](https://pypi.org/project/tefas-client/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/tefas-client.svg)](https://pypi.org/project/tefas-client/)
[![PyPI - License](https://img.shields.io/pypi/l/tefas-client.svg)](LICENSE)
[![CI](https://github.com/semudu/tefas-client/actions/workflows/ci.yml/badge.svg)](https://github.com/semudu/tefas-client/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-latest-blue.svg)](https://github.com/semudu/tefas-client#readme)

**tefas-client** is a type-safe Python client for real-time fund data from [TEFAS](https://www.tefas.gov.tr) (Türkiye Elektronik Fon Alım Satım Platformu).

Fetch fund prices, allocations, and metrics with a simple, synchronous API. Perfect for building financial dashboards, analysis tools, and investment tracking apps.

> **Stable v1 API** — Production-ready, fully tested, zero breaking changes.

## Features

- **📊 Real-time data**: Fund prices (NAV), market cap, investor counts
- **🔍 Portfolio breakdown**: Asset allocation across thousands of securities  
- **⏱️ Smart chunking**: Automatic handling of TEFAS's 28-day query limits
- **🛡️ Type-safe**: Full Pydantic validation, mypy compatible
- **⚡ Resilient**: Exponential backoff, automatic weekend date handling
- **🐍 Modern Python**: 3.10+ with context manager support

## Installation

```bash
pip install tefas-client
```

### Other package managers

```bash
# uv
uv pip install tefas-client

# Poetry
poetry add tefas-client

# Conda
conda install -c conda-forge tefas-client
```

## Quick start

```python
from datetime import date
from tefas_client import Tefas

# Basic usage – single fund
with Tefas() as tefas:
    funds = tefas.fetch("AAK", start_date=date(2024, 2, 1), end_date=date(2024, 2, 1))
    fund = funds["AAK"]
    print(f"{fund.title}: {fund.latest().price} TRY")
    # Output: Ak Portfoy Amerikan Dolar Yabanci BYF: 23.456789 TRY
```

## Usage Examples

### Basic: Fetch latest price

```python
from datetime import date, timedelta
from tefas_client import Tefas

with Tefas(timeout=15.0) as tefas:
    today = date.today()
    funds = tefas.fetch("AAK", start_date=today, end_date=today)
    latest = funds["AAK"].latest()
    print(f"Price: {latest.price}")
    print(f"Market Cap: {latest.market_cap} TRY")
    print(f"Investors: {latest.number_of_investors}")
```

### Advanced: Date range with allocation

```python
from datetime import date
from tefas_client import Tefas

with Tefas() as tefas:
    # Fetch 3-month history with portfolio breakdown
    funds = tefas.fetch(
        "AAK",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 3, 31),
        include_allocation=True,
    )
    
    for history in funds["AAK"].history:
        print(f"{history.date}: {history.price} TRY")
        
        if history.allocation:
            print("  Top holdings:")
            for code in list(history.allocation.assets.keys())[:3]:
                pct = history.allocation.assets[code]
                name = history.allocation.asset_names[code]
                print(f"    {name}: {pct:.2f}%")
```

### Batch: Multiple funds at once

```python
from datetime import date
from tefas_client import Tefas

fund_codes = ["AAK", "AAFTIYTF", "AKBLV"]

with Tefas() as tefas:
    # Fetch all funds at once (empty code = all available funds)
    all_funds = tefas.fetch(start_date=date(2024, 2, 1), end_date=date(2024, 2, 28))
    
    # Filter to codes of interest
    for code in fund_codes:
        if code in all_funds:
            fund = all_funds[code]
            price = fund.latest().price
            print(f"{code}: {price}")
```

### Integration: Export to Pandas

```python
import pandas as pd
from datetime import date
from tefas_client import Tefas

with Tefas() as tefas:
    funds = tefas.fetch("AAK", start_date=date(2024, 1, 1), end_date=date(2024, 3, 31))
    
    # Convert to DataFrame
    df = pd.DataFrame([
        {
            "date": h.date,
            "price": h.price,
            "market_cap": h.market_cap,
            "investors": h.number_of_investors,
        }
        for h in funds["AAK"].history
    ])
    
    print(df.describe())
```

### Error handling

```python
from tefas_client import Tefas, RateLimitError, EmptyResponseError

try:
    with Tefas() as tefas:
        funds = tefas.fetch("INVALID")
except EmptyResponseError:
    print("No data for this date range")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds")
```

## API reference

### `Tefas(timeout: float = 30.0)`

Context manager for managing HTTP connections and sessions.

```python
with Tefas(timeout=15.0) as tefas:
    funds = tefas.fetch("AAK", start_date=date.today(), end_date=date.today())
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `timeout` | `float` | `30.0` | Per-request HTTP timeout in seconds |

### `Tefas.fetch(fund_code: str = "", *, start_date: date | None = None, end_date: date | None = None, include_allocation: bool = False) -> dict[str, Fund]`

Fetch fund data for a given date range.

```python
with Tefas() as tefas:
    # Single fund
    funds = tefas.fetch("AAK", start_date=date(2024, 1, 1), end_date=date(2024, 3, 31))
    
    # All funds
    all_funds = tefas.fetch(start_date=date.today(), end_date=date.today())
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `fund_code` | `str` | `""` | TEFAS code (e.g. `"AAK"`). Empty = all funds |
| `start_date` | `date \| None` | `end_date` | Inclusive range start. Defaults to `end_date` |
| `end_date` | `date \| None` | today | Inclusive range end. Automatically adjusted to nearest Friday if weekend/holiday |
| `include_allocation` | `bool` | `False` | Include portfolio allocation breakdown |

**Returns:** `dict[str, Fund]` — mapping of fund code → fund data

### `Fund`

Represents a single fund.

```python
fund: Fund
fund.code          # "AAK"
fund.title         # "Ak Portfoy Amerikan Dolar Yabanci BYF"
fund.latest()      # History (most recent entry)
fund.history       # list[History] (all historical entries, oldest first)
```

| Attribute | Type | Description |
|-----------|------|-------------|
| `code` | `str` | TEFAS fund code (e.g. "AAK") |
| `title` | `str` | Full fund name in Turkish |
| `history` | `list[History]` | Chronological price/metric history, oldest first |

### `History`

Single fund snapshot for a trading date.

```python
h: History
h.price                    # Fund unit price (NAV) in TRY
h.market_cap              # Portfolio value in TRY
h.number_of_investors     # Active investor count
h.allocation              # Allocation data (if requested)
```

| Field | Type | Description |
|-------|------|-------------|
| `date` | `date` | Trading date (never a weekend/holiday) |
| `price` | `float \| None` | Fund unit price (NAV) in TRY |
| `market_cap` | `float \| None` | Portfolio size (TRY) |
| `number_of_shares` | `float \| None` | Total circulating shares |
| `number_of_investors` | `int \| None` | Active investor count |
| `exchange_bulletin_price` | `float \| None` | Exchange bulletin price (BYF only) |
| `allocation` | `Allocation \| None` | Portfolio breakdown (if `include_allocation=True`) |

### `Allocation`

Portfolio composition snapshot.

```python
a: Allocation
a.assets           # {"US0378331005": 45.5, "IE00B4L5Y983": 30.2, ...}
a.asset_names      # {"US0378331005": "APPLE INC.", ...}
```

| Field | Type | Description |
|-------|------|-------------|
| `date` | `date` | Allocation date |
| `assets` | `dict[str, float]` | `{ISIN: percentage_allocation}` |
| `asset_names` | `dict[str, str]` | `{ISIN: security_name}` |

## Exceptions

All exceptions inherit from `TefasError` and can be caught with:

```python
from tefas_client import Tefas, TefasError

try:
    with Tefas() as tefas:
        funds = tefas.fetch("AAK", start_date=date(2024, 1, 1))
except TefasError as e:
    print(f"TEFAS error: {e}")
```

| Exception | When | Example |
|-----------|------|---------|
| `TefasError` | Base class for all library errors | `except TefasError: pass` |
| `RateLimitError` | HTTP 429 after retries (has `retry_after` attribute) | `except RateLimitError as e: time.sleep(e.retry_after)` |
| `EmptyResponseError` | API returned 200 but no rows for query | `except EmptyResponseError: print("No data")` |

## Known Constraints

| Constraint | Impact | Workaround |
|-----------|--------|-----------|
| **Rate limit** | ~6 req/min, retries with backoff, raises after 3 failures | Space requests ≥10s apart, use batch queries |
| **28-day window** | Max query is ~28 calendar days | Automatic; `fetch()` chunks larger ranges |
| **No weekend data** | TEFAS closed weekends/holidays | Dates auto-adjust to nearest Friday |
| **WAF/IP blocks** | Datacenter IPs may get 403/503 | Use residential IP or VPN |
| **Synchronous only** | No built-in async/await | Use `asyncio.to_thread()` if needed (advanced) |

## Troubleshooting

### "403 Forbidden" or "503 Service Unavailable"

**Cause:** TEFAS WAF blocks datacenter IP ranges (AWS, Azure, etc.)

**Solution:**
- Use a residential VPN or local ISP connection
- For production: Use a proxy service with residential IPs
- The library auto-retries; wait a few seconds before trying again

### "RateLimitError: Retry after X seconds"

**Cause:** Too many requests to TEFAS API (>6/min)

**Solution:**
```python
import time
from tefas_client import Tefas, RateLimitError

with Tefas() as tefas:
    for fund_code in ["AAK", "AAFTIYTF", "AKBLV"]:
        try:
            funds = tefas.fetch(fund_code, start_date=date.today(), end_date=date.today())
        except RateLimitError as e:
            print(f"Rate limited. Waiting {e.retry_after}s...")
            time.sleep(e.retry_after + 1)  # +1 for safety margin
            # Retry logic here
```

### "EmptyResponseError"

**Cause:** No trading data for that date (e.g., weekend, holiday, fund didn't exist)

**Solution:**
```python
from tefas_client import Tefas, EmptyResponseError

try:
    with Tefas() as tefas:
        # Try a date range instead of single day
        funds = tefas.fetch("AAK", start_date=date(2024, 1, 1), end_date=date(2024, 1, 10))
except EmptyResponseError:
    print("No data available; fund may not have existed or dates were all holidays")
```

### Slow performance

**Tip 1:** Use context manager (reuses connection across multiple `fetch()` calls)
```python
# ✅ Good: single connection for 3 calls
with Tefas() as tefas:
    funds1 = tefas.fetch("AAK", ...)
    funds2 = tefas.fetch("AAFTIYTF", ...)
    funds3 = tefas.fetch("AKBLV", ...)
```

**Tip 2:** Fetch all funds in one call instead of per-code
```python
# ✅ Good: 1 request
with Tefas() as tefas:
    all_funds = tefas.fetch(start_date=date.today(), end_date=date.today())  
    tefas_funds = {k: v for k, v in all_funds.items() if k.startswith("AAFTI")}

# ❌ Avoid: 3 requests
with Tefas() as tefas:
    funds1 = tefas.fetch("AAK", ...)
    funds2 = tefas.fetch("AAFTIYTF", ...)
    funds3 = tefas.fetch("AKBLV", ...)
```

**Tip 3:** Use shorter date ranges
```python
# ✅ Good: smaller response, faster
with Tefas() as tefas:
    funds = tefas.fetch("AAK", start_date=date(2024, 1, 1), end_date=date(2024, 1, 31))

# ❌ Slow: year of data
with Tefas() as tefas:
    funds = tefas.fetch("AAK", start_date=date(2023, 1, 1), end_date=date(2024, 12, 31))
```

## Contributing

We welcome contributions! To get started:

```bash
# Clone and install
git clone https://github.com/semudu/tefas-client
cd tefas-client
make install

# Run tests
make test

# Lint and format
make lint
make format
```

**Development workflow:**
- Fork the repository on GitHub
- Create a feature branch: `git checkout -b feature/my-feature`
- Make your changes and ensure tests pass (`make test`)
- Commit: `git commit -am "Add my feature"`
- Push and open a pull request

**Code style:**
- Python 3.10+ with type hints
- Ruff for formatting and linting
- Mypy for static type checking
- Pytest for testing

See [CONTRIBUTING.md](CONTRIBUTING.md) (if available) or open an issue to discuss ideas.

## License

[MIT](LICENSE) — Free for personal and commercial use

---

<div align="center">

**Questions?** [Open an issue](https://github.com/semudu/tefas-client/issues)  
**Found a bug?** [Report it](https://github.com/semudu/tefas-client/issues/new)  
**Have a feature idea?** [Suggest it](https://github.com/semudu/tefas-client/discussions)

</div>
