"""Manuel deneme scripti — .gitignore'da, commit edilmez."""
from datetime import date

from src.tefas_client import Tefas

START = date(2025, 1, 1)
END = date(2025, 1, 10)

# Context manager: bağlantı iki fetch arasında paylaşılır
with Tefas() as tefas:
    # YAT fonu (otomatik algılama — fonTipi belirtilmeden)
    yat_funds = tefas.fetch("AAK", start_date=START, end_date=END, include_allocation=True)

    # EMK / BES fonu (otomatik algılama — fonTipi belirtilmeden)
    emk_funds = tefas.fetch("HHY", start_date=START, end_date=END)

    # Birden fazla kod bir çağrıda
    multi = tefas.fetch(["AAK", "TLY"], start_date=START, end_date=END, fund_type="YAT")

for code, fund in {**yat_funds, **emk_funds}.items():
    print(f"\n{code}: {fund.title}")
    latest = fund.latest()
    print(f"  Son tarih : {latest.date}")
    print(f"  Fiyat     : {latest.price}")
    print(f"  Piyasa değ: {latest.market_cap}")
    if latest.allocation:
        print("  Dağılım (top 5):")
        for asset, pct in sorted(
            latest.allocation.assets.items(), key=lambda x: x[1], reverse=True
        )[:5]:
            name = latest.allocation.asset_names.get(asset, asset)
            print(f"    {name}: {pct:.2f}%")

print(f"\nÇoklu sorgu: {list(multi.keys())}")
