import argparse
import csv
from pathlib import Path

from quant_system.config import get_fmp_api_key
from quant_system.fmp_client import FmpClient
from quant_system.run_universe import load_symbols


DEFAULT_CACHE_DIR = "quant_system/cache/historical"


ENDPOINTS = [
    (
        "profile",
        "profile",
        {},
        "profiles.csv",
    ),
    (
        "income_statement_quarterly",
        "income-statement",
        {"period": "quarter", "limit": 40},
        "income_statement_quarterly.csv",
    ),
    (
        "cash_flow_quarterly",
        "cash-flow-statement",
        {"period": "quarter", "limit": 40},
        "cash_flow_quarterly.csv",
    ),
    (
        "balance_sheet_quarterly",
        "balance-sheet-statement",
        {"period": "quarter", "limit": 40},
        "balance_sheet_quarterly.csv",
    ),
    (
        "prices_daily",
        "historical-price-eod/full",
        {},
        "prices_daily.csv",
    ),
]


def main():
    parser = argparse.ArgumentParser(description="Build local historical FMP cache.")
    parser.add_argument(
        "--symbols",
        help="Comma-separated symbols, for example: AAPL,MSFT,NVDA.",
    )
    parser.add_argument(
        "--universe",
        help="CSV or text file with one symbol per row, or a CSV column named symbol.",
    )
    parser.add_argument(
        "--cache-dir",
        default=DEFAULT_CACHE_DIR,
        help="Directory for historical cache CSV files.",
    )
    parser.add_argument("--limit", type=int, help="Only run the first N symbols.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Fetch symbols even if they already appear in the profile cache.",
    )
    parser.add_argument(
        "--max-consecutive-failures",
        type=int,
        default=25,
        help="Stop the run after this many consecutive failures. Use 0 to disable.",
    )
    args = parser.parse_args()

    symbols = load_symbols(args.symbols, args.universe)
    if args.limit:
        symbols = symbols[: args.limit]
    if not symbols:
        raise RuntimeError("No symbols provided. Use --symbols or --universe.")

    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    completed = set() if args.force else read_completed_symbols(cache_dir)
    client = FmpClient(get_fmp_api_key())
    failures = []
    consecutive_failures = 0

    print(f"Building historical cache for {len(symbols)} symbols...")
    print(f"Cache directory: {cache_dir}")

    for index, symbol in enumerate(symbols, start=1):
        if symbol in completed:
            print(f"[{index}/{len(symbols)}] {symbol}: skipped, already cached")
            continue

        try:
            fetched = fetch_symbol(client, symbol)
            write_symbol_cache(fetched, cache_dir)
            append_rows(cache_dir / "completed_historical.csv", [{"symbol": symbol}])
            completed.add(symbol)
            consecutive_failures = 0
            print(f"[{index}/{len(symbols)}] {symbol}: cached")
        except Exception as error:
            print(f"[{index}/{len(symbols)}] {symbol}: failed - {error}")
            failures.append({"symbol": symbol, "error": str(error)})
            consecutive_failures += 1
            if (
                args.max_consecutive_failures > 0
                and consecutive_failures >= args.max_consecutive_failures
            ):
                print(
                    "Stopping after "
                    f"{consecutive_failures} consecutive failures. "
                    "Check network/API status, then rerun to continue."
                )
                break

    if failures:
        append_rows(cache_dir / "failed_historical.csv", failures)

    print(f"Done. failures={len(failures)}")


def read_completed_symbols(cache_dir):
    completed_path = cache_dir / "completed_historical.csv"
    if completed_path.exists():
        with completed_path.open("r", encoding="utf-8-sig", newline="") as file:
            return {
                row.get("symbol", "").strip().upper()
                for row in csv.DictReader(file)
                if row.get("symbol")
            }

    return infer_completed_symbols(cache_dir)


def infer_completed_symbols(cache_dir):
    symbol_sets = []
    for _, _, _, filename in ENDPOINTS:
        path = cache_dir / filename
        if path.exists():
            symbol_sets.append(read_symbols(path))

    if not symbol_sets:
        return set()

    return set.intersection(*symbol_sets)


def read_symbols(path):
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return {
            row.get("symbol", "").strip().upper()
            for row in csv.DictReader(file)
            if row.get("symbol")
        }


def fetch_symbol(client, symbol):
    fetched = []

    for _, endpoint, params, filename in ENDPOINTS:
        request_params = {"symbol": symbol, **params}
        data = client.get(endpoint, request_params)
        rows = normalize_rows(symbol, data)
        if not rows:
            raise RuntimeError(f"{endpoint} returned no rows")
        fetched.append((filename, rows))

    return fetched


def write_symbol_cache(fetched, cache_dir):
    for filename, rows in fetched:
        append_rows(cache_dir / filename, rows)


def normalize_rows(symbol, data):
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = [data]
    else:
        rows = []

    normalized = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append({"symbol": symbol, **row})

    return normalized


def append_rows(path, rows):
    if not rows:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = merged_fieldnames(path, rows)
    existing_rows = read_existing_rows(path) if path.exists() else []

    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in existing_rows:
            writer.writerow(row)
        for row in rows:
            writer.writerow(row)


def merged_fieldnames(path, new_rows):
    fieldnames = []
    if path.exists():
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            fieldnames.extend(reader.fieldnames or [])

    for row in new_rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    return fieldnames


def read_existing_rows(path):
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


if __name__ == "__main__":
    main()
