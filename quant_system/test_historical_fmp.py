import argparse

from quant_system.config import get_fmp_api_key
from quant_system.fmp_client import FmpClient


CHECKS = [
    (
        "quarterly income statement",
        "income-statement",
        {"period": "quarter", "limit": 40},
    ),
    (
        "quarterly cash flow statement",
        "cash-flow-statement",
        {"period": "quarter", "limit": 40},
    ),
    (
        "quarterly balance sheet",
        "balance-sheet-statement",
        {"period": "quarter", "limit": 40},
    ),
    (
        "quarterly ratios",
        "ratios",
        {"period": "quarter", "limit": 40},
    ),
    (
        "daily historical prices",
        "historical-price-eod/full",
        {},
    ),
]


def main():
    parser = argparse.ArgumentParser(description="Test FMP historical data availability.")
    parser.add_argument("--symbol", default="AAPL", help="Symbol to test.")
    args = parser.parse_args()

    client = FmpClient(get_fmp_api_key())
    symbol = args.symbol.strip().upper()

    print(f"Testing historical FMP data for {symbol}...")
    for label, endpoint, params in CHECKS:
        test_endpoint(client, symbol, label, endpoint, params)


def test_endpoint(client, symbol, label, endpoint, params):
    request_params = {"symbol": symbol, **params}

    try:
        data = client.get(endpoint, request_params)
    except Exception as error:
        print(f"FAIL {label}: {error}")
        return

    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = [data]
    else:
        rows = []

    if not rows:
        print(f"FAIL {label}: no rows returned")
        return

    first = rows[0]
    last = rows[-1]
    first_date = first.get("date") or first.get("fillingDate") or first.get("filingDate")
    last_date = last.get("date") or last.get("fillingDate") or last.get("filingDate")
    fields = sorted(first.keys())[:12]
    print(
        f"OK   {label}: rows={len(rows)}, first_date={first_date}, "
        f"last_date={last_date}, sample_fields={fields}"
    )


if __name__ == "__main__":
    main()
