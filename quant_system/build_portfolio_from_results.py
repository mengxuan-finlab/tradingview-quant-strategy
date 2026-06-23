import argparse
import csv
from pathlib import Path

from quant_system.portfolio import DEFAULT_PORTFOLIO, build_portfolio
from quant_system.run_universe import PORTFOLIO_COLUMNS, write_results


NUMERIC_COLUMNS = {
    "strategy_score",
    "price",
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
}


BOOLEAN_COLUMNS = {
    "pass_strategy",
    "is_etf",
    "is_fund",
    "is_adr",
    "is_actively_trading",
}


def main():
    parser = argparse.ArgumentParser(
        description="Build final portfolio from an existing valuation_results.csv."
    )
    parser.add_argument(
        "--input",
        default="quant_system/output/valuation_results.csv",
        help="Existing valuation results CSV path.",
    )
    parser.add_argument(
        "--output",
        default="quant_system/output/portfolio_results.csv",
        help="Portfolio output CSV path.",
    )
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
    args = parser.parse_args()

    results = read_results(args.input)
    portfolio = build_portfolio(
        results,
        {
            "portfolio_size": args.portfolio_size,
            "max_sector_count": args.max_sector_count,
            "max_industry_count": args.max_industry_count,
            "require_positive_upside": not args.allow_negative_dcf_upside,
        },
    )
    write_results(portfolio, args.output, fieldnames=PORTFOLIO_COLUMNS)

    if portfolio:
        print(
            f"Wrote {len(portfolio)} portfolio rows to {args.output}; "
            f"target_weight={1 / len(portfolio):.2%}"
        )
    else:
        print(f"Wrote 0 portfolio rows to {args.output}")


def read_results(input_path):
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Valuation results file not found: {input_path}")

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [coerce_row(row) for row in csv.DictReader(file)]


def coerce_row(row):
    clean = dict(row)

    for column in NUMERIC_COLUMNS:
        clean[column] = parse_float(clean.get(column))
    for column in BOOLEAN_COLUMNS:
        clean[column] = parse_bool(clean.get(column))

    return clean


def parse_float(value):
    if value in (None, ""):
        return 0.0
    return float(value)


def parse_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


if __name__ == "__main__":
    main()
