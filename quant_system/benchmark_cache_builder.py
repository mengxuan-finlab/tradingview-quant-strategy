import argparse
import csv
from pathlib import Path

from quant_system.config import get_fmp_api_key
from quant_system.fmp_client import FmpClient


DEFAULT_SYMBOLS = "SPY,QQQ"
DEFAULT_OUTPUT = "quant_system/cache/historical/benchmark_prices_daily.csv"


def main():
    parser = argparse.ArgumentParser(description="Build benchmark daily price cache.")
    parser.add_argument(
        "--symbols",
        default=DEFAULT_SYMBOLS,
        help="Comma-separated benchmark symbols, for example: SPY,QQQ.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help="Benchmark price cache CSV path.",
    )
    args = parser.parse_args()

    client = FmpClient(get_fmp_api_key())
    symbols = [symbol.strip().upper() for symbol in args.symbols.split(",") if symbol.strip()]
    rows = []
    failures = []

    for symbol in symbols:
        try:
            data = client.get("historical-price-eod/full", {"symbol": symbol})
            symbol_rows = normalize_rows(symbol, data)
            if not symbol_rows:
                raise RuntimeError("historical-price-eod/full returned no rows")
            rows.extend(symbol_rows)
            print(f"{symbol}: cached {len(symbol_rows)} price rows")
        except Exception as error:
            failures.append({"symbol": symbol, "error": str(error)})
            print(f"{symbol}: failed - {error}")

    write_rows(Path(args.output), rows)
    if failures:
        failure_path = Path(args.output).with_name("failed_benchmarks.csv")
        write_rows(failure_path, failures)
        print(f"Wrote {len(failures)} failed benchmarks to {failure_path}")

    print(f"Wrote {len(rows)} benchmark price rows to {args.output}")


def normalize_rows(symbol, data):
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = [data]
    else:
        rows = []

    return [
        {"symbol": symbol, **row}
        for row in rows
        if isinstance(row, dict)
    ]


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = merged_fieldnames(rows)

    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def merged_fieldnames(rows):
    fieldnames = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    return fieldnames


if __name__ == "__main__":
    main()
