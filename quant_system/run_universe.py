import argparse
import csv
from pathlib import Path

from quant_system.config import get_fmp_api_key
from quant_system.data_pipeline import fetch_fundamental_snapshot
from quant_system.fmp_client import FmpClient
from quant_system.valuation_engine import value_stock


OUTPUT_COLUMNS = [
    "symbol",
    "price",
    "fair_value",
    "upside",
    "score",
    "wacc",
    "fcf_growth",
    "free_cash_flow",
    "market_cap",
    "beta",
    "roic",
    "debt_to_equity",
]


def main():
    parser = argparse.ArgumentParser(description="Run fundamental quant valuation.")
    parser.add_argument(
        "--symbols",
        help="Comma-separated symbols, for example: AAPL,MSFT,NVDA",
    )
    parser.add_argument(
        "--universe",
        help="CSV or text file with one symbol per row, or a CSV column named symbol.",
    )
    parser.add_argument(
        "--output",
        default="quant_system/output/valuation_results.csv",
        help="CSV output path.",
    )
    parser.add_argument("--limit", type=int, help="Only run the first N symbols.")
    parser.add_argument("--risk-free-rate", type=float, default=0.04)
    parser.add_argument("--market-return", type=float, default=0.10)
    parser.add_argument("--terminal-growth-rate", type=float, default=0.03)
    parser.add_argument("--tax-rate", type=float, default=0.21)
    args = parser.parse_args()

    symbols = load_symbols(args.symbols, args.universe)
    if args.limit:
        symbols = symbols[: args.limit]

    if not symbols:
        raise RuntimeError("No symbols provided. Use --symbols or --universe.")

    client = FmpClient(get_fmp_api_key())
    results = []

    print(f"Running {len(symbols)} symbols...")

    for index, symbol in enumerate(symbols, start=1):
        try:
            snapshot = fetch_fundamental_snapshot(client, symbol)
            result = value_stock(
                snapshot,
                risk_free_rate=args.risk_free_rate,
                market_return=args.market_return,
                terminal_growth_rate=args.terminal_growth_rate,
                tax_rate=args.tax_rate,
            )
            results.append(result)
            print(
                f"[{index}/{len(symbols)}] {symbol}: "
                f"fair_value={result['fair_value']:.2f}, "
                f"upside={result['upside']:.2%}, score={result['score']:.2f}"
            )
        except Exception as error:
            print(f"[{index}/{len(symbols)}] {symbol}: failed - {error}")

    results.sort(key=lambda item: item["score"], reverse=True)
    write_results(results, args.output)
    print(f"Wrote {len(results)} rows to {args.output}")


def load_symbols(symbols_arg, universe_path):
    symbols = []

    if symbols_arg:
        symbols.extend(symbol.strip().upper() for symbol in symbols_arg.split(","))

    if universe_path:
        symbols.extend(read_universe_file(universe_path))

    return dedupe_symbols(symbols)


def read_universe_file(universe_path):
    path = Path(universe_path)
    if not path.exists():
        raise FileNotFoundError(f"Universe file not found: {universe_path}")

    rows = path.read_text(encoding="utf-8-sig").splitlines()
    rows = [row.strip() for row in rows if row.strip()]
    if not rows:
        return []

    first_row = rows[0].lower().replace("\ufeff", "")
    if "," in rows[0] or first_row == "symbol":
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames and "symbol" in [name.lower() for name in reader.fieldnames]:
                symbol_column = next(name for name in reader.fieldnames if name.lower() == "symbol")
                return [row[symbol_column].strip().upper() for row in reader]

    return [row.split(",")[0].strip().upper() for row in rows if row.strip().lower() != "symbol"]


def dedupe_symbols(symbols):
    seen = set()
    clean_symbols = []

    for symbol in symbols:
        clean_symbol = symbol.strip().upper()
        if not clean_symbol or clean_symbol in seen:
            continue

        seen.add(clean_symbol)
        clean_symbols.append(clean_symbol)

    return clean_symbols


def write_results(results, output_path):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for result in results:
            writer.writerow({column: result.get(column, "") for column in OUTPUT_COLUMNS})


if __name__ == "__main__":
    main()
