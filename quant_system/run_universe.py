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
        required=True,
        help="Comma-separated symbols, for example: AAPL,MSFT,NVDA",
    )
    parser.add_argument(
        "--output",
        default="quant_system/output/valuation_results.csv",
        help="CSV output path.",
    )
    parser.add_argument("--risk-free-rate", type=float, default=0.04)
    parser.add_argument("--market-return", type=float, default=0.10)
    parser.add_argument("--terminal-growth-rate", type=float, default=0.03)
    parser.add_argument("--tax-rate", type=float, default=0.21)
    args = parser.parse_args()

    client = FmpClient(get_fmp_api_key())
    symbols = [symbol.strip().upper() for symbol in args.symbols.split(",") if symbol.strip()]
    results = []

    for symbol in symbols:
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
                f"{symbol}: fair_value={result['fair_value']:.2f}, "
                f"upside={result['upside']:.2%}, score={result['score']:.2f}"
            )
        except Exception as error:
            print(f"{symbol}: failed - {error}")

    results.sort(key=lambda item: item["score"], reverse=True)
    write_results(results, args.output)
    print(f"Wrote {len(results)} rows to {args.output}")


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
