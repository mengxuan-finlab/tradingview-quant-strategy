import argparse
import csv
from pathlib import Path

from quant_system.config import get_fmp_api_key
from quant_system.data_pipeline import fetch_fundamental_snapshot
from quant_system.fmp_client import FmpClient
from quant_system.portfolio import DEFAULT_PORTFOLIO, build_portfolio
from quant_system.strategy import apply_quality_value_strategy
from quant_system.valuation_engine import value_stock


OUTPUT_COLUMNS = [
    "symbol",
    "pass_strategy",
    "strategy_score",
    "research_priority",
    "reject_reasons",
    "price",
    "company_name",
    "sector",
    "industry",
    "exchange",
    "is_etf",
    "is_fund",
    "is_adr",
    "is_actively_trading",
    "fair_value",
    "upside",
    "score",
    "wacc",
    "dcf_growth_rate",
    "growth_estimate",
    "revenue_growth",
    "fcf_growth",
    "eps_growth",
    "momentum_3m",
    "momentum_6m",
    "momentum_12m",
    "free_cash_flow",
    "market_cap",
    "beta",
    "roic",
    "debt_to_equity",
    "strategy",
]


PORTFOLIO_COLUMNS = [
    "portfolio_rank",
    "target_weight",
    *OUTPUT_COLUMNS,
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
    parser.add_argument(
        "--portfolio-output",
        default="quant_system/output/portfolio_results.csv",
        help="CSV output path for the final portfolio after position constraints.",
    )
    parser.add_argument(
        "--failed-output",
        default="quant_system/output/failed_symbols.csv",
        help="CSV output path for symbols that failed during data collection or valuation.",
    )
    parser.add_argument("--limit", type=int, help="Only run the first N symbols.")
    parser.add_argument(
        "--portfolio-size",
        type=int,
        default=DEFAULT_PORTFOLIO["portfolio_size"],
        help="Maximum number of stocks in the final portfolio.",
    )
    parser.add_argument(
        "--max-sector-count",
        type=int,
        default=DEFAULT_PORTFOLIO["max_sector_count"],
        help="Maximum number of portfolio stocks from one sector.",
    )
    parser.add_argument(
        "--max-industry-count",
        type=int,
        default=DEFAULT_PORTFOLIO["max_industry_count"],
        help="Maximum number of portfolio stocks from one industry.",
    )
    parser.add_argument(
        "--allow-negative-dcf-upside",
        action="store_true",
        help="Allow stocks with negative DCF upside into the final portfolio.",
    )
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
    failures = []

    print(f"Running {len(symbols)} symbols...")

    for index, symbol in enumerate(symbols, start=1):
        try:
            snapshot = fetch_fundamental_snapshot(client, symbol)
            valuation = value_stock(
                snapshot,
                risk_free_rate=args.risk_free_rate,
                market_return=args.market_return,
                terminal_growth_rate=args.terminal_growth_rate,
                tax_rate=args.tax_rate,
            )
            result = apply_quality_value_strategy(valuation)
            results.append(result)
            status = "PASS" if result["pass_strategy"] else "FAIL"
            print(
                f"[{index}/{len(symbols)}] {symbol}: {status}, "
                f"fair_value={result['fair_value']:.2f}, "
                f"upside={result['upside']:.2%}, "
                f"strategy_score={result['strategy_score']:.2f}, research={result['research_priority']}"
            )
        except Exception as error:
            print(f"[{index}/{len(symbols)}] {symbol}: failed - {error}")
            failures.append({"symbol": symbol, "error": str(error)})

    results.sort(
        key=lambda item: (item["pass_strategy"], item["strategy_score"]),
        reverse=True,
    )
    write_results(results, args.output)
    portfolio = build_portfolio(
        results,
        {
            "portfolio_size": args.portfolio_size,
            "max_sector_count": args.max_sector_count,
            "max_industry_count": args.max_industry_count,
            "require_positive_upside": not args.allow_negative_dcf_upside,
        },
    )
    write_results(portfolio, args.portfolio_output, fieldnames=PORTFOLIO_COLUMNS)
    write_failures(failures, args.failed_output)
    passed_count = sum(1 for result in results if result["pass_strategy"])
    print(f"Wrote {len(results)} rows to {args.output}; {passed_count} passed strategy")
    print(
        f"Wrote {len(portfolio)} portfolio rows to {args.portfolio_output}; "
        f"target_weight={1 / len(portfolio):.2%}" if portfolio else
        f"Wrote 0 portfolio rows to {args.portfolio_output}"
    )
    print(f"Wrote {len(failures)} failed symbols to {args.failed_output}")


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


def write_results(results, output_path, fieldnames=None):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = fieldnames or OUTPUT_COLUMNS

    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow({column: result.get(column, "") for column in fieldnames})


def write_failures(failures, output_path):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["symbol", "error"])
        writer.writeheader()
        writer.writerows(failures)


if __name__ == "__main__":
    main()







