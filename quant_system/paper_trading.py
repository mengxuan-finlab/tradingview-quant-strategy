import argparse
import csv
from datetime import date
from pathlib import Path

from quant_system.build_portfolio_from_results import read_results
from quant_system.portfolio import DEFAULT_PORTFOLIO, build_portfolio


DEFAULT_INPUT = "quant_system/output/valuation_results.csv"
DEFAULT_OUTPUT = "quant_system/output/paper_top15.csv"
DEFAULT_STRATEGY_NAME = "top15_qg6_value9_sector2"


PAPER_COLUMNS = [
    "paper_date",
    "strategy_name",
    "symbol",
    "target_weight",
    "portfolio_rank",
    "portfolio_sleeve",
    "price",
    "company_name",
    "sector",
    "industry",
    "exchange",
    "strategy_score",
    "research_priority",
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
    "pass_strategy",
    "reject_reasons",
    "notes",
]


def main():
    parser = argparse.ArgumentParser(
        description="Build a paper-trading portfolio from valuation_results.csv."
    )
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--strategy-name", default=DEFAULT_STRATEGY_NAME)
    parser.add_argument(
        "--paper-date",
        default=date.today().isoformat(),
        help="Paper trading snapshot date, default is today.",
    )
    parser.add_argument(
        "--portfolio-size",
        type=int,
        default=15,
        help="Top15 candidate strategy portfolio size.",
    )
    parser.add_argument(
        "--quality-growth-sleeve-size",
        type=int,
        default=6,
    )
    parser.add_argument(
        "--value-sleeve-size",
        type=int,
        default=9,
    )
    parser.add_argument(
        "--max-sector-count",
        type=int,
        default=2,
    )
    parser.add_argument(
        "--max-industry-count",
        type=int,
        default=1,
    )
    args = parser.parse_args()

    results = read_results(args.input)
    config = {
        **DEFAULT_PORTFOLIO,
        "portfolio_size": args.portfolio_size,
        "quality_growth_sleeve_size": args.quality_growth_sleeve_size,
        "value_sleeve_size": args.value_sleeve_size,
        "max_sector_count": args.max_sector_count,
        "max_industry_count": args.max_industry_count,
    }
    portfolio = build_portfolio(results, config)
    rows = [
        build_paper_row(
            stock=stock,
            paper_date=args.paper_date,
            strategy_name=args.strategy_name,
        )
        for stock in portfolio
    ]

    write_rows(Path(args.output), rows)
    print(
        f"Wrote {len(rows)} paper trading rows to {args.output}; "
        f"strategy={args.strategy_name}"
    )
    if rows:
        print(f"target_weight={float(rows[0]['target_weight']):.2%}")


def build_paper_row(stock, paper_date, strategy_name):
    row = {
        "paper_date": paper_date,
        "strategy_name": strategy_name,
        "notes": "",
    }
    for column in PAPER_COLUMNS:
        if column in row:
            continue
        row[column] = stock.get(column, "")
    return row


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=PAPER_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in PAPER_COLUMNS})


if __name__ == "__main__":
    main()
